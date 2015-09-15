#!/usr/bin/python2.7

import httplib2
import os
from apiclient import discovery
from apiclient import errors
from apiclient import http
import pyinotify
import oauth2client
from oauth2client import client
from oauth2client import tools
import pprint

GDRIVE_FOLDER = 'gdrive'

try:
    import argparse

    flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
except ImportError:
    flags = None

SCOPES = 'https://www.googleapis.com/auth/drive'
CLIENT_SECRET_FILE = 'client_secret.json'
APPLICATION_NAME = 'Drive API Quickstart'


class EventHandler(pyinotify.ProcessEvent):

    def process_IN_CREATE(self, event):
        print "Creating:", event.pathname
        service = get_drive_service()
        if os.path.isdir(event.pathname):
            for dirPath, subdirList, fileList in os.walk(event.pathname):
                dirName = dirPath.split(os.path.sep)[-1]
                parentDirName = dirPath.split(os.path.sep)[-2]
                print 'dirPath: %s | dirName:%s' % (dirPath, dirName)
                parent_id = get_file_id(service, parentDirName)
                print parent_id
                dir = insert_dir(service, dirName, dirPath, parent_id)
                parent_id = dir['id']
                for fname in fileList:
                    path = os.path.join(dirPath, fname)
                    print 'fname:%s | fpath:%s' % (fname, path)
                    insert_file(service, fname, path, parent_id)
        print 'Files created'

    def process_IN_MOVED_TO(self, event):
        print event.name

    def process_IN_CLOSE_WRITE(self, event):
        print "Closing:", event.pathname
        service = get_drive_service()
        if os.path.isfile(event.pathname):
            insert_file(service, event.name, event.pathname)

    def process_IN_DELETE(self, event):
        print "Deleting:", event.pathname
        service = get_drive_service()
        file_id = get_file_id(service, event.name)
        if file_id:
            delete_file(service, file_id)

    def process_IN_MODIFY(self, event):
        print "Changing:", event.pathname
        service = get_drive_service()
        insert_file(service, event.name, event.pathname)


def get_credentials():
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.quickstart
    """

    credential_dir = os.path.dirname(os.path.realpath(__file__))
    credential_path = os.path.join(credential_dir, 'credentials.json')
    store = oauth2client.file.Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(os.path.join(credential_dir, CLIENT_SECRET_FILE), SCOPES)
        flow.user_agent = APPLICATION_NAME
        if flags:
            credentials = tools.run_flow(flow, store, flags)
        else:  # Needed only for compatability with Python 2.6
            credentials = tools.run(flow, store)
        print 'Storing credentials to ' + credential_path
    return credentials

def download_file(service, file_id, local_fd):
    """Download a Drive file's content to the local filesystem.

    Args:
      service: Drive API Service instance.
      file_id: ID of the Drive file that will downloaded.
      local_fd: io.Base or file object, the stream that the Drive file's
          contents will be written to.
    """
    request = service.files().get_media(fileId=file_id)
    media_request = http.MediaIoBaseDownload(local_fd, request)

    while True:
        try:
            download_progress, done = media_request.next_chunk()
        except errors.HttpError, error:
            print 'An error occurred: %s' % error
            return
        if download_progress:
            print 'Download Progress: %d%%' % int(download_progress.progress() * 100)
        if done:
            print 'Download Complete'
            return


def insert_dir(service, title, dirname, parent_id=None):
    print "inserting:", dirname
    body = {
        'title': title,
        'mimeType': 'application/vnd.google-apps.folder'
    }
    if parent_id:
        body['parents'] = [{'id': parent_id}]
    try:
        dir = service.files().insert(body=body).execute()
        return dir
    except errors.HttpError, error:
        print 'An error occured while inserting: %s' % error
        return None


def insert_file(service, title, filename, parent_id=None):
    body = {
        'title': title,
        'uploadType': 'media'
    }
    if parent_id:
        body['parents'] = [{'id': parent_id}]
    media_body = http.MediaFileUpload(filename, mimetype='*/*')
    try:
        file = service.files().insert(
            body=body,
            media_body=media_body).execute()
        return file
    except errors.HttpError, error:
        print 'An error occured: %s' % error
        return None


def delete_file(service, file_id):
    """Permanently delete a file, skipping the trash.

    Args:
      service: Drive API service instance.
      file_id: ID of the file to delete.
    """
    try:
        service.files().delete(fileId=file_id).execute()
    except errors.HttpError, error:
        print 'An error occurred: %s' % error


def get_drive_service():
    credentials = get_credentials()
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('drive', 'v2', http=http)
    return service


def get_file_id(service, name):
    result = []
    page_token = None
    while True:
        try:
            param = {}
            param['q'] = "title = '%s'" % name
            if page_token:
                param['pageToken'] = page_token
            files = service.files().list(**param).execute()
            result.extend(files['items'])
            page_token = files.get('nextPageToken')
            if not page_token:
                break
        except errors.HttpError, error:
            print 'An error occurred: %s' % error
            break
    if result:
        return result[0]['id']
    return None


def watch():
    wm = pyinotify.WatchManager()

    mask = pyinotify.IN_DELETE | pyinotify.IN_CLOSE_WRITE | pyinotify.IN_MODIFY | pyinotify.IN_MOVED_TO | pyinotify.IN_CREATE

    handler = EventHandler()
    notifier = pyinotify.Notifier(wm, handler)
    user_home_folder = os.path.join(os.path.expanduser('~'), GDRIVE_FOLDER) 
    wdd = wm.add_watch(user_home_folder, mask, rec=True)
    notifier.loop()


def main():
    watch()


if __name__ == '__main__':
    main()
