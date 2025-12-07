"""
S3 Connector for bulk ingestion.

Discovers and syncs files from AWS S3 buckets.
"""

import os
import logging
import mimetypes
from typing import Optional, List, Dict, Any, Generator
from dataclasses import dataclass

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)


@dataclass
class S3Config:
    """S3 connector configuration."""
    access_key_id: str
    secret_access_key: str
    bucket_name: str
    prefix: str = ""
    region: str = "us-east-1"


class S3Connector:
    """
    Connects to AWS S3 and discovers files for ingestion.
    
    Supports:
    - Bucket listing with prefix filtering
    - Pagination for large buckets
    - File metadata extraction
    - Content streaming for large files
    """
    
    ALLOWED_EXTENSIONS = ['.txt', '.md', '.json', '.csv', '.pdf', '.doc', '.docx', 
                          '.xls', '.xlsx', '.ppt', '.pptx', '.rtf', '.html', '.xml']
    
    def __init__(self, config: S3Config):
        self.config = config
        self._client = None
    
    @property
    def client(self):
        """Lazy-load S3 client."""
        if self._client is None:
            self._client = boto3.client(
                's3',
                aws_access_key_id=self.config.access_key_id,
                aws_secret_access_key=self.config.secret_access_key,
                region_name=self.config.region
            )
        return self._client
    
    def test_connection(self) -> Dict[str, Any]:
        """Test S3 connection and return bucket info."""
        try:
            response = self.client.head_bucket(Bucket=self.config.bucket_name)
            
            paginator = self.client.get_paginator('list_objects_v2')
            total_objects = 0
            total_size = 0
            
            for page in paginator.paginate(
                Bucket=self.config.bucket_name,
                Prefix=self.config.prefix,
                MaxKeys=1000
            ):
                if 'Contents' in page:
                    total_objects += len(page['Contents'])
                    total_size += sum(obj['Size'] for obj in page['Contents'])
                
                if total_objects >= 1000:
                    break
            
            return {
                'success': True,
                'bucket': self.config.bucket_name,
                'prefix': self.config.prefix,
                'objects_sample': total_objects,
                'size_sample_mb': round(total_size / 1024 / 1024, 2)
            }
            
        except NoCredentialsError:
            return {'success': False, 'error': 'Invalid AWS credentials'}
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == '403':
                return {'success': False, 'error': 'Access denied to bucket'}
            elif error_code == '404':
                return {'success': False, 'error': 'Bucket not found'}
            return {'success': False, 'error': f'S3 error: {error_code}'}
        except Exception as e:
            logger.error(f"S3 connection test failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def discover_files(self, max_files: int = 10000) -> Generator[Dict[str, Any], None, None]:
        """
        Discover files in the S3 bucket.
        
        Yields file metadata dicts with:
        - key: S3 object key
        - name: filename
        - size: file size in bytes
        - mime_type: guessed MIME type
        - last_modified: last modified timestamp
        - etag: S3 ETag (can be used for change detection)
        """
        paginator = self.client.get_paginator('list_objects_v2')
        files_found = 0
        
        for page in paginator.paginate(
            Bucket=self.config.bucket_name,
            Prefix=self.config.prefix
        ):
            if 'Contents' not in page:
                continue
            
            for obj in page['Contents']:
                if files_found >= max_files:
                    return
                
                key = obj['Key']
                
                if key.endswith('/'):
                    continue
                
                filename = os.path.basename(key)
                if not filename:
                    continue
                
                ext = os.path.splitext(filename)[1].lower()
                if ext not in self.ALLOWED_EXTENSIONS:
                    continue
                
                mime_type, _ = mimetypes.guess_type(filename)
                
                yield {
                    'key': key,
                    'name': filename,
                    'size': obj['Size'],
                    'mime_type': mime_type or 'application/octet-stream',
                    'last_modified': obj['LastModified'].isoformat(),
                    'etag': obj['ETag'].strip('"'),
                    'external_id': f"s3://{self.config.bucket_name}/{key}"
                }
                
                files_found += 1
    
    def get_file_content(self, key: str) -> bytes:
        """Download file content from S3."""
        response = self.client.get_object(
            Bucket=self.config.bucket_name,
            Key=key
        )
        return response['Body'].read()
    
    def get_file_stream(self, key: str):
        """Get streaming body for large files."""
        response = self.client.get_object(
            Bucket=self.config.bucket_name,
            Key=key
        )
        return response['Body']


def create_s3_connector_from_encrypted(encrypted_config: bytes, encryption) -> S3Connector:
    """Create S3 connector from encrypted configuration."""
    config_dict = encryption.decrypt_config(encrypted_config)
    config = S3Config(
        access_key_id=config_dict['access_key_id'],
        secret_access_key=config_dict['secret_access_key'],
        bucket_name=config_dict['bucket_name'],
        prefix=config_dict.get('prefix', ''),
        region=config_dict.get('region', 'us-east-1')
    )
    return S3Connector(config)
