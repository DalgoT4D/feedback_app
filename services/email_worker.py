#!/usr/bin/env python3
"""
Email worker to process queued emails from the database.
This script processes 50 emails at a time and prevents multiple instances from running.
Designed to be run every 5 minutes via system cron/timer.
"""

import sys
import os
import time
import fcntl
from datetime import datetime

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from services.db_helper import get_connection
from services.email_service import _send_email_sync
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Lock file for preventing multiple instances
LOCK_FILE = "/tmp/email_worker.lock"

class WorkerLock:
    """Context manager for email worker lock to prevent multiple instances."""
    
    def __init__(self, lock_file=LOCK_FILE):
        self.lock_file = lock_file
        self.lock_fd = None
    
    def __enter__(self):
        try:
            self.lock_fd = open(self.lock_file, 'w')
            fcntl.flock(self.lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.lock_fd.write(f"{os.getpid()}\n{datetime.now().isoformat()}\n")
            self.lock_fd.flush()
            logger.info(f"Acquired lock: {self.lock_file}")
            return self
        except (IOError, OSError) as e:
            if self.lock_fd:
                self.lock_fd.close()
            logger.warning(f"Could not acquire lock {self.lock_file}: {e}")
            raise
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.lock_fd:
            fcntl.flock(self.lock_fd.fileno(), fcntl.LOCK_UN)
            self.lock_fd.close()
            try:
                os.remove(self.lock_file)
                logger.info(f"Released lock: {self.lock_file}")
            except OSError:
                pass  # Lock file may have been removed already

def get_pending_emails(batch_size=50):
    """Get pending emails from queue."""
    conn = get_connection()
    try:
        result = conn.execute("""
            SELECT id, to_email, subject, html_body, text_body, email_type, attempts
            FROM email_queue 
            WHERE status = 'pending' AND attempts < 3
            ORDER BY created_at ASC
            LIMIT ?
        """, (batch_size,))
        return result.fetchall()
    except Exception as e:
        logger.error(f"Error fetching pending emails: {e}")
        return []

def mark_email_processed(email_id, success, error_message=None):
    """Mark email as processed in the queue."""
    conn = get_connection()
    try:
        if success:
            conn.execute("""
                UPDATE email_queue 
                SET status = 'sent', last_attempt = CURRENT_TIMESTAMP, attempts = attempts + 1
                WHERE id = ?
            """, (email_id,))
        else:
            conn.execute("""
                UPDATE email_queue 
                SET status = CASE WHEN attempts >= 2 THEN 'failed' ELSE 'pending' END,
                    last_attempt = CURRENT_TIMESTAMP, 
                    attempts = attempts + 1,
                    error_message = ?
                WHERE id = ?
            """, (error_message, email_id))
        conn.commit()
        logger.info(f"Email {email_id} marked as {'sent' if success else 'failed/retry'}")
    except Exception as e:
        logger.error(f"Error updating email status: {e}")

def process_email_queue():
    """Process exactly 50 pending emails from the queue."""
    logger.info("Starting email queue processing (max 50 emails)...")
    
    pending_emails = get_pending_emails(50)
    
    if not pending_emails:
        logger.info("No pending emails to process")
        return 0
    
    logger.info(f"Processing {len(pending_emails)} emails")
    processed_count = 0
    
    for email_data in pending_emails:
        email_id, to_email, subject, html_body, text_body, email_type, attempts = email_data
        
        logger.info(f"Processing email {email_id} to {to_email} (attempt {attempts + 1})")
        
        try:
            success, error_msg = _send_email_sync(
                to_email=to_email,
                subject=subject,
                html_body=html_body,
                text_body=text_body,
                email_type=email_type
            )
            
            mark_email_processed(email_id, success, error_msg)
            
            if success:
                logger.info(f"✓ Email {email_id} sent successfully to {to_email}")
            else:
                logger.warning(f"✗ Email {email_id} failed: {error_msg}")
            
            processed_count += 1
            
            # Small delay between emails to avoid overwhelming the SMTP server
            time.sleep(0.5)
            
        except Exception as e:
            logger.error(f"Exception processing email {email_id}: {e}")
            mark_email_processed(email_id, False, str(e))
            processed_count += 1
            
    logger.info(f"Email queue processing completed: {processed_count} emails processed")
    return processed_count

def run_worker_once():
    """Run the worker once to process pending emails with lock protection."""
    try:
        with WorkerLock():
            logger.info("=== EMAIL WORKER STARTING ===")
            processed = process_email_queue()
            logger.info(f"=== EMAIL WORKER COMPLETED: {processed} emails processed ===")
            return processed
    except (IOError, OSError):
        logger.info("Another email worker is already running, skipping this execution")
        return 0

def run_worker_daemon(interval=300):
    """Run the worker continuously with specified interval (default 5 minutes)."""
    logger.info(f"Starting email worker daemon (checking every {interval}s)")
    
    while True:
        try:
            run_worker_once()
            time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("Worker daemon stopped by user")
            break
        except Exception as e:
            logger.error(f"Worker daemon error: {e}")
            time.sleep(interval)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Email worker for processing queued emails')
    parser.add_argument('--daemon', action='store_true', help='Run as daemon (continuous processing)')
    parser.add_argument('--interval', type=int, default=30, help='Check interval in seconds (daemon mode only)')
    
    args = parser.parse_args()
    
    if args.daemon:
        run_worker_daemon(args.interval)
    else:
        run_worker_once()
