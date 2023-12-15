#!/usr/bin/python
import os
import subprocess
import shutil
from datetime import date

import http.client
import httplib2
import random
import sys
import time

from apiclient.discovery import build
from apiclient.errors import HttpError
from apiclient.http import MediaFileUpload
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import argparser, run_flow

# Explicitly tell the underlying HTTP transport library not to retry, since
# we are handling retry logic ourselves.
httplib2.RETRIES = 1

# Maximum number of times to retry before giving up.
MAX_RETRIES = 10

# Always retry when these exceptions are raised.
RETRIABLE_EXCEPTIONS = (httplib2.HttpLib2Error, IOError, http.client.NotConnected,
  http.client.IncompleteRead, http.client.ImproperConnectionState,
  http.client.CannotSendRequest, http.client.CannotSendHeader,
  http.client.ResponseNotReady, http.client.BadStatusLine)

# Always retry when an apiclient.errors.HttpError with one of these status
# codes is raised.
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]

# The CLIENT_SECRETS_FILE variable specifies the name of a file that contains
# the OAuth 2.0 information for this application, including its client_id and
# client_secret. You can acquire an OAuth 2.0 client ID and client secret from
# the Google API Console at
# https://console.cloud.google.com/.
# Please ensure that you have enabled the YouTube Data API for your project.
# For more information about using OAuth2 to access the YouTube Data API, see:
#   https://developers.google.com/youtube/v3/guides/authentication
# For more information about the client_secrets.json file format, see:
#   https://developers.google.com/api-client-library/python/guide/aaa_client_secrets
CLIENT_SECRETS_FILE = "client_secrets.json"

# This OAuth 2.0 access scope allows an application to upload files to the
# authenticated user's YouTube channel, but doesn't allow other types of access.
YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

# This variable defines a message to display if the CLIENT_SECRETS_FILE is
# missing.
MISSING_CLIENT_SECRETS_MESSAGE = """
警告: OAuth 2.0を設定してください

APIコンソール(https://console.cloud.google.com/)の情報をもとにclient_secrets.jsonを埋めたうえで次のディレクトリに配置してください:

   %s

client_secrets.jsonフォーマットについての詳しい情報は次のページを確認してください:
https://developers.google.com/api-client-library/python/guide/aaa_client_secrets
""" % os.path.abspath(os.path.join(os.path.dirname(__file__),
                                   CLIENT_SECRETS_FILE))

VALID_PRIVACY_STATUSES = ("public", "private", "unlisted")

#experimental
upload_file = ""
upload_title = "default"
upload_description = ""
upload_categoryId = "22"
upload_keywords = ""
upload_privacyStatus = "unlisted"

def get_authenticated_service(args):
  flow = flow_from_clientsecrets(CLIENT_SECRETS_FILE,
    scope=YOUTUBE_UPLOAD_SCOPE,
    message=MISSING_CLIENT_SECRETS_MESSAGE)

  storage = Storage("%s-oauth2.json" % sys.argv[0])
  credentials = storage.get()

  if credentials is None or credentials.invalid:
    credentials = run_flow(flow, storage, args)

  return build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION,
    http=credentials.authorize(httplib2.Http()))

def initialize_upload(youtube, video_file, video_title, video_keywords, video_description, video_categoryId, video_privacyStatus):
  tags = None


  body=dict(
    snippet=dict(
      title=video_title,
      description=video_description,
      tags=tags,
      categoryId=video_categoryId
    ),
    status=dict(
      privacyStatus=video_privacyStatus
    )
  )

  # Call the API's videos.insert method to create and upload the video.
  insert_request = youtube.videos().insert(
    part=",".join(list(body.keys())),
    body=body,
    # The chunksize parameter specifies the size of each chunk of data, in
    # bytes, that will be uploaded at a time. Set a higher value for
    # reliable connections as fewer chunks lead to faster uploads. Set a lower
    # value for better recovery on less reliable connections.
    #
    # Setting "chunksize" equal to -1 in the code below means that the entire
    # file will be uploaded in a single HTTP request. (If the upload fails,
    # it will still be retried where it left off.) This is usually a best
    # practice, but if you're using Python older than 2.6 or if you're
    # running on App Engine, you should set the chunksize to something like
    # 1024 * 1024 (1 megabyte).
    media_body=MediaFileUpload(video_file, chunksize=-1, resumable=True)
  )

  resumable_upload(insert_request, video_title)

# This method implements an exponential backoff strategy to resume a
# failed upload.
def resumable_upload(insert_request, video_title):
  response = None
  error = None
  retry = 0
  while response is None:
    try:
      print("%sをアップロード中", %　video_title)
      status, response = insert_request.next_chunk()
      if response is not None:
        if 'id' in response:
          print("「%s」のアップロードに成功しました（Video ID:%s）" % (video_title, response['id']))
        else:
          exit("エラーによりアップロードが失敗しました:%s" % response)
    except HttpError as e:
      if e.resp.status in RETRIABLE_STATUS_CODES:
        error = "再試行可能なHTTPエラー(%d)が発生しました:\n%s" % (e.resp.status,
                                                             e.content)
      else:
        raise
    except RETRIABLE_EXCEPTIONS as e:
      error = "再試行可能なエラーが発生しました: %s" % e

    if error is not None:
      print(error)
      retry += 1
      if retry > MAX_RETRIES:
        exit("再試行の回数の上限を超えました")

      max_sleep = 2 ** retry
      sleep_seconds = random.random() * max_sleep
      print("%f秒間のスリープ後に再開します..." % sleep_seconds)
      time.sleep(sleep_seconds)

args = argparser.parse_args()

# ディレクトリ情報を取得
parent_parent_dir = os.getcwd()

# 大学名の入力、フォルダ作成、作業（？）ディレクトリの移動
univ_name = input("大学名？")
date = str(date.today())
univ_folder_name = date + " " + univ_name
path = os.path.join(parent_parent_dir, univ_folder_name)
if not (os.path.exists(path)):
  os.mkdir(path)
os.chdir(path)
parent_dir = os.getcwd()

# ダブルス、シングルスの本数を入力
num_doubles = int(input("ダブルスの本数？"))
num_singles = int(input("シングルスの本数？"))

# フォルダ作成の際に使用する変数
num_default = 1
str_default = ""
num = ""
member1 = ""
member2 = ""
folder_name = ""

folder_path_list = []
file_name_wo_num_list = []
file_name_wo_num = ""

# ダブルスフォルダ作成
for i in range(num_doubles):
  str_default = str(num_default)
  num = "D" + str_default
  member1 = input("%sの一人目の名前？" % num)
  member2 = input("%sの二人目の名前？" % num)
  folder_name = num + " " + member1 + " " + member2
  path = os.path.join(parent_dir, folder_name)
  if not (os.path.exists(path)):
    os.mkdir(path)
  folder_path_list.append(path)
  file_name_wo_num = univ_name + " " + folder_name
  file_name_wo_num_list.append(file_name_wo_num)
  num_default = num_default + 1

# 数字のリセット
num_default = 1

# シングルスフォルダ作成
for i in range(num_singles):
  str_default = str(num_default)
  num = "S" + str_default
  member1 = input("%sの名前？" % num)
  folder_name = num + " " + member1
  path = os.path.join(parent_dir, folder_name)
  if not (os.path.exists(path)):
    os.mkdir(path)
  folder_path_list.append(path)
  file_name_wo_num = univ_name + " " + folder_name
  file_name_wo_num_list.append(file_name_wo_num)
  num_default = num_default + 1

# 作成したフォルダをエクスプローラーで開く
open_explorer = 'explorer.exe ' + '/root,"' + parent_dir + '"'
print(open_explorer)
subprocess.run(open_explorer)

# 動画のコピー待ち
print("フォルダに動画をコピーしてください")
input("完了したらエンターキーを押してください")

# ファイル名変更用のリスト
file_list = []

# 数字のリセット
num_default = 1

# 動画のファイル名変更
for i in range(num_doubles + num_singles):
  path = folder_path_list[i]
  os.chdir(path)
  file_list = os.listdir(path)
  file_list.sort()

  for n in file_list:
    file_body, file_ext = os.path.splitext(n) #rename
    file_name = file_name_wo_num_list[i] + " " + str(num_default) + file_ext
    file_path = os.path.join(path, file_name)
    os.rename(n, file_path)

    os.chdir(parent_parent_dir)
    youtube = get_authenticated_service(args) #upload to youtube
    upload_file = file_path
    upload_title = file_name
    try:
      initialize_upload(youtube, upload_file, upload_title, upload_keywords, upload_description, upload_categoryId,
                        upload_privacyStatus)
    except HttpError as e:
      print("An HTTP error %d occurred:\n%s" % (e.resp.status, e.content))
    os.chdir(path)

    num_default = num_default + 1

  num_default = 1

print("ファイル名変更が完了しました")