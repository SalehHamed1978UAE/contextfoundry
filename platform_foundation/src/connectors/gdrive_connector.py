"""
Google Drive Connector for bulk ingestion.

Uses OAuth 2.0 for user authentication and Google Drive API for file discovery.
"""

import os
import io
import logging
import mimetypes
from typing import Optional, List, Dict, Any, Generator
from dataclasses import dataclass

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

EXPORT_MIME_TYPES = {
    'application/vnd.google-apps.document': ('application/pdf', '.pdf'),
    'application/vnd.google-apps.spreadsheet': ('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', '.xlsx'),
    'application/vnd.google-apps.presentation': ('application/vnd.openxmlformats-officedocument.presentationml.presentation', '.pptx'),
}


@dataclass
class GDriveConfig:
    """Google Drive connector configuration."""
    access_token: str
    refresh_token: str
    token_uri: str = "https://oauth2.googleapis.com/token"
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    folder_id: Optional[str] = None


class GDriveConnector:
    """
    Connects to Google Drive and discovers files for ingestion.
    
    Supports:
    - Folder listing with recursive traversal
    - Google Docs export to PDF/Office formats
    - File metadata extraction
    - Content streaming
    """
    
    ALLOWED_EXTENSIONS = ['.txt', '.md', '.json', '.csv', '.pdf', '.doc', '.docx', 
                          '.xls', '.xlsx', '.ppt', '.pptx', '.rtf', '.html', '.xml']
    
    MAX_FILE_SIZE = 50 * 1024 * 1024
    
    def __init__(self, config: GDriveConfig):
        self.config = config
        self._service = None
    
    @property
    def service(self):
        """Lazy-load Drive service."""
        if self._service is None:
            creds = Credentials(
                token=self.config.access_token,
                refresh_token=self.config.refresh_token,
                token_uri=self.config.token_uri,
                client_id=self.config.client_id,
                client_secret=self.config.client_secret
            )
            self._service = build('drive', 'v3', credentials=creds)
        return self._service
    
    def test_connection(self) -> Dict[str, Any]:
        """Test Google Drive connection and return account info."""
        try:
            about = self.service.about().get(fields="user,storageQuota").execute()
            user = about.get('user', {})
            quota = about.get('storageQuota', {})
            
            results = self.service.files().list(
                pageSize=1,
                q=self._build_query(),
                fields="files(id)"
            ).execute()
            
            return {
                'success': True,
                'email': user.get('emailAddress'),
                'name': user.get('displayName'),
                'storage_used_gb': round(int(quota.get('usage', 0)) / 1024**3, 2),
                'has_files': len(results.get('files', [])) > 0
            }
            
        except HttpError as e:
            if e.resp.status == 401:
                return {'success': False, 'error': 'Authentication expired - please reconnect'}
            elif e.resp.status == 403:
                return {'success': False, 'error': 'Access denied - check permissions'}
            return {'success': False, 'error': f'Google API error: {e.resp.status}'}
        except Exception as e:
            logger.error(f"Google Drive connection test failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def _build_query(self) -> str:
        """Build file query with optional folder filter."""
        conditions = ["trashed = false"]
        
        if self.config.folder_id:
            conditions.append(f"'{self.config.folder_id}' in parents")
        
        return " and ".join(conditions)
    
    def discover_files(self, max_files: int = 10000, recursive: bool = True) -> Generator[Dict[str, Any], None, None]:
        """
        Discover files in Google Drive.
        
        Yields file metadata dicts with:
        - id: Google Drive file ID
        - name: filename
        - size: file size in bytes
        - mime_type: MIME type
        - modified_time: last modified timestamp
        - is_google_doc: whether it's a native Google doc
        """
        files_found = 0
        
        folders_to_scan = [self.config.folder_id] if self.config.folder_id else [None]
        
        while folders_to_scan and files_found < max_files:
            current_folder = folders_to_scan.pop(0)
            
            query = "trashed = false"
            if current_folder:
                query += f" and '{current_folder}' in parents"
            
            page_token = None
            while files_found < max_files:
                try:
                    results = self.service.files().list(
                        pageSize=100,
                        q=query,
                        fields="nextPageToken, files(id, name, mimeType, size, modifiedTime, parents)",
                        pageToken=page_token
                    ).execute()
                except HttpError as e:
                    logger.error(f"Error listing files: {e}")
                    break
                
                for file in results.get('files', []):
                    if files_found >= max_files:
                        return
                    
                    mime_type = file.get('mimeType', '')
                    
                    if mime_type == 'application/vnd.google-apps.folder':
                        if recursive:
                            folders_to_scan.append(file['id'])
                        continue
                    
                    is_google_doc = mime_type in EXPORT_MIME_TYPES
                    
                    if is_google_doc:
                        export_mime, export_ext = EXPORT_MIME_TYPES[mime_type]
                        name = file['name'] + export_ext
                        effective_mime = export_mime
                        size = 0
                    else:
                        name = file['name']
                        effective_mime = mime_type
                        size = int(file.get('size', 0))
                        
                        ext = os.path.splitext(name)[1].lower()
                        if ext not in self.ALLOWED_EXTENSIONS:
                            continue
                        
                        if size > self.MAX_FILE_SIZE:
                            continue
                    
                    yield {
                        'id': file['id'],
                        'name': name,
                        'size': size,
                        'mime_type': effective_mime,
                        'modified_time': file.get('modifiedTime'),
                        'is_google_doc': is_google_doc,
                        'original_mime': mime_type,
                        'external_id': f"gdrive://{file['id']}"
                    }
                    
                    files_found += 1
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
    
    def get_file_content(self, file_id: str, is_google_doc: bool = False, 
                        original_mime: str = None) -> bytes:
        """Download file content from Google Drive."""
        try:
            if is_google_doc and original_mime in EXPORT_MIME_TYPES:
                export_mime, _ = EXPORT_MIME_TYPES[original_mime]
                request = self.service.files().export_media(
                    fileId=file_id,
                    mimeType=export_mime
                )
            else:
                request = self.service.files().get_media(fileId=file_id)
            
            buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(buffer, request)
            
            done = False
            while not done:
                _, done = downloader.next_chunk()
            
            return buffer.getvalue()
            
        except HttpError as e:
            logger.error(f"Error downloading file {file_id}: {e}")
            raise


def create_gdrive_connector_from_encrypted(encrypted_config: bytes, encryption) -> GDriveConnector:
    """Create Google Drive connector from encrypted configuration."""
    config_dict = encryption.decrypt_config(encrypted_config)
    config = GDriveConfig(
        access_token=config_dict['access_token'],
        refresh_token=config_dict['refresh_token'],
        token_uri=config_dict.get('token_uri', 'https://oauth2.googleapis.com/token'),
        client_id=config_dict.get('client_id'),
        client_secret=config_dict.get('client_secret'),
        folder_id=config_dict.get('folder_id')
    )
    return GDriveConnector(config)
