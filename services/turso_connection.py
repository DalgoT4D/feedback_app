"""
Turso Database Connection Module
Clean implementation using turso-python for ARM compatibility
"""

import streamlit as st
from turso_python import TursoClient
from typing import Optional, List, Dict, Any, Union
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TursoResult:
    """
    Compatibility layer to provide familiar database result interface
    """
    
    def __init__(self, turso_response: Dict[str, Any]):
        self._response = turso_response
        self._process_response()
        self._current_index = 0
    
    def _process_response(self):
        """Process turso-python response format into familiar structure"""
        self._rows = []
        self._columns = []
        self.rowcount = 0
        
        try:
            if 'results' in self._response and self._response['results']:
                result = self._response['results'][0]
                if result['type'] == 'ok' and 'response' in result:
                    response = result['response']
                    if response['type'] == 'execute' and 'result' in response:
                        result_data = response['result']
                        
                        # Extract column information
                        if 'cols' in result_data:
                            self._columns = [col['name'] for col in result_data['cols']]
                        
                        # Extract and process rows
                        if 'rows' in result_data and result_data['rows']:
                            for row in result_data['rows']:
                                processed_row = []
                                for cell in row:
                                    if isinstance(cell, dict) and 'value' in cell:
                                        # Convert string values back to appropriate types
                                        value = cell['value']
                                        if cell.get('type') == 'integer':
                                            value = int(value) if value is not None else None
                                        elif cell.get('type') == 'real':
                                            value = float(value) if value is not None else None
                                        elif cell.get('type') == 'null':
                                            value = None
                                        # 'text' and other types remain as strings
                                        processed_row.append(value)
                                    else:
                                        processed_row.append(cell)
                                self._rows.append(tuple(processed_row))
                        
                        # Set affected row count
                        self.rowcount = result_data.get('affected_row_count', len(self._rows))
                        
        except Exception as e:
            logger.error(f"Error processing Turso response: {e}")
            self._rows = []
            self._columns = []
    
    def fetchone(self) -> Optional[tuple]:
        """Fetch next row as tuple (compatible with libsql_experimental)"""
        if self._current_index < len(self._rows):
            row = self._rows[self._current_index]
            self._current_index += 1
            return row
        return None
    
    def fetchall(self) -> List[tuple]:
        """Fetch all remaining rows as list of tuples"""
        remaining = self._rows[self._current_index:]
        self._current_index = len(self._rows)
        return remaining
    
    def fetchmany(self, size: int) -> List[tuple]:
        """Fetch up to size rows"""
        end_index = min(self._current_index + size, len(self._rows))
        rows = self._rows[self._current_index:end_index]
        self._current_index = end_index
        return rows
    
    @property
    def description(self):
        """Column descriptions (for compatibility)"""
        return [(col, None, None, None, None, None, None) for col in self._columns]


class TursoConnection:
    """
    Database connection class using turso-python
    Provides interface compatible with the existing codebase
    """
    
    def __init__(self, database_url: str, auth_token: str):
        self.database_url = database_url
        self.auth_token = auth_token
        self._client = None
        self._connect()
    
    def _connect(self):
        """Initialize the Turso client"""
        try:
            self._client = TursoClient(
                database_url=self.database_url,
                auth_token=self.auth_token
            )
            logger.info("Successfully connected to Turso database")
        except Exception as e:
            logger.error(f"Failed to connect to Turso database: {e}")
            raise
    
    def execute(self, query: str, parameters: Optional[Union[tuple, list]] = None) -> TursoResult:
        """
        Execute SQL query with optional parameters
        
        Args:
            query: SQL query string
            parameters: Optional query parameters
            
        Returns:
            TursoResult: Compatible result object
        """
        try:
            if parameters:
                # Handle parameterized queries
                # Convert tuple/list parameters to the format expected by turso-python
                if isinstance(parameters, (tuple, list)):
                    # For positional parameters, we need to replace ? with actual values
                    # This is a simplified approach - in production, you might want more sophisticated parameter handling
                    formatted_query = query
                    for param in parameters:
                        if isinstance(param, str):
                            formatted_query = formatted_query.replace('?', f"'{param}'", 1)
                        else:
                            formatted_query = formatted_query.replace('?', str(param), 1)
                    
                    response = self._client.execute_query(formatted_query)
                else:
                    response = self._client.execute_query(query)
            else:
                response = self._client.execute_query(query)
            
            return TursoResult(response)
            
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Parameters: {parameters}")
            raise
    
    def commit(self):
        """Commit transaction (no-op for turso-python as it auto-commits)"""
        pass
    
    def rollback(self):
        """Rollback transaction (limited support in turso-python)"""
        logger.warning("Rollback not fully supported with turso-python")
        pass
    
    def close(self):
        """Close the connection"""
        self._client = None
        logger.info("Turso connection closed")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def get_connection() -> TursoConnection:
    """
    Get a database connection using Turso credentials
    Drop-in replacement for the previous get_connection() function
    """
    try:
        db_url = st.secrets["DB_URL"]
        auth_token = st.secrets["AUTH_TOKEN"]
        
        if not db_url or not auth_token:
            raise ValueError("Missing database credentials in Streamlit secrets")
        
        return TursoConnection(db_url, auth_token)
        
    except Exception as e:
        logger.error(f"Failed to create database connection: {e}")
        raise


def test_connection() -> bool:
    """Test the database connection"""
    try:
        with get_connection() as conn:
            result = conn.execute("SELECT 1 as test")
            row = result.fetchone()
            return row is not None and row[0] == 1
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        return False


if __name__ == "__main__":
    # Test the connection module
    print("Testing Turso connection module...")
    
    if test_connection():
        print("✅ Connection test passed!")
        
        # Test a real query
        try:
            with get_connection() as conn:
                result = conn.execute("SELECT COUNT(*) FROM review_cycles")
                count = result.fetchone()
                print(f"✅ Found {count[0]} review cycles in database")
        except Exception as e:
            print(f"❌ Real query test failed: {e}")
    else:
        print("❌ Connection test failed!")