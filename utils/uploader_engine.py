import os
import pickle
import threading
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from instagrapi import Client

# YouTube scopes for uploading videos
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def upload_to_youtube(video_path, title, description, tags, category_id="22"):
    """
    Uploads a video to YouTube Shorts using the official Google API.
    Requires 'client_secrets.json' to be in the root directory.
    """
    try:
        creds = None
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        token_path = os.path.join(base_dir, 'token.pickle')
        client_secrets_path = os.path.join(base_dir, 'client_secrets.json')

        if os.path.exists(token_path):
            with open(token_path, 'rb') as token:
                creds = pickle.load(token)
                
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(client_secrets_path):
                    return {"success": False, "error": "client_secrets.json missing. You need to download it from Google Cloud Console."}
                
                flow = InstalledAppFlow.from_client_secrets_file(client_secrets_path, YOUTUBE_SCOPES)
                # This will open a browser for the user to authenticate the first time
                creds = flow.run_local_server(port=0)
            
            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)

        youtube = build("youtube", "v3", credentials=creds)

        # Split tags string by space and remove #
        tags_list = [t.replace("#", "") for t in tags.split(" ") if t]

        body = {
            "snippet": {
                "title": title,
                "description": f"{description}\n\n{tags}",
                "tags": tags_list,
                "categoryId": category_id
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False
            }
        }

        insert_request = youtube.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=MediaFileUpload(video_path, chunksize=-1, resumable=True)
        )

        response = insert_request.execute()
        return {"success": True, "video_id": response.get("id")}
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def upload_to_instagram(video_path, title, description, tags, username, password, session_id=None):
    """
    Uploads a Reel to Instagram using the unofficial instagrapi library.
    """
    try:
        if not username and not session_id:
            return {"success": False, "error": "Instagram credentials or session ID missing."}
            
        cl = Client()
        
        if session_id:
            cl.login_by_sessionid(session_id)
        else:
            # Check for cached session to prevent repetitive logins
            session_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), f"insta_session_{username}.json")
            
            if os.path.exists(session_file):
                cl.load_settings(session_file)
                
            cl.login(username, password)
            cl.dump_settings(session_file)
        
        caption = f"{title}\n\n{description}\n\n{tags}"
        
        import subprocess
        import pathlib
        thumb_path = video_path + ".jpg"
        ffmpeg_exe = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ffmpeg.exe")
        if not os.path.exists(ffmpeg_exe):
            ffmpeg_exe = "ffmpeg"
        subprocess.run([ffmpeg_exe, "-i", video_path, "-ss", "00:00:01", "-vframes", "1", thumb_path, "-y"], capture_output=True)
        
        # Upload as a Reel
        media = cl.clip_upload(pathlib.Path(video_path), caption, thumbnail=pathlib.Path(thumb_path))
        return {"success": True, "media_pk": media.pk}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def upload_to_tiktok(video_path, title, description, tags, session_id):
    """
    Uploads a video to TikTok using tiktok-uploader (requires sessionid cookie).
    """
    try:
        if not session_id:
            return {"success": False, "error": "TikTok session_id cookie missing."}
            
        from tiktok_uploader.upload import upload_video
        
        caption = f"{title} {description} {tags}"
        
        # We need to construct a temp cookies.txt for the uploader
        temp_cookies_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tiktok_cookies.txt')
        with open(temp_cookies_path, 'w') as f:
            if "tiktok.com" in session_id or "# Netscape" in session_id:
                # User pasted the full cookies.txt content
                f.write(session_id)
            else:
                # User pasted just the sessionid, fallback to generating it
                f.write("# Netscape HTTP Cookie File\n")
                f.write(f".tiktok.com\tTRUE\t/\tFALSE\t2272828000\tsessionid\t{session_id}\n")
                f.write(f"www.tiktok.com\tFALSE\t/\tFALSE\t2272828000\tsessionid\t{session_id}\n")
            
        failed = upload_video(video_path, description=caption, cookies=temp_cookies_path)
        
        if failed:
            return {"success": False, "error": "TikTok upload failed according to the uploader script."}
            
        return {"success": True}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def process_auto_uploads(video_path, seo_data, config, results_callback):
    """
    Orchestrates the uploads in parallel to save time.
    """
    results = {}
    threads = []
    
    title = seo_data.get('title', '')
    desc = seo_data.get('description', '')
    tags = seo_data.get('hashtags', '')

    def run_yt():
        if config.get("youtube_enabled"):
            results["youtube"] = upload_to_youtube(video_path, title, desc, tags)
        else:
            results["youtube"] = {"success": False, "error": "Skipped"}
            
    def run_ig():
        if config.get("insta_enabled"):
            results["instagram"] = upload_to_instagram(
                video_path, title, desc, tags,
                config.get("insta_username"), config.get("insta_password"),
                config.get("insta_session_id")
            )
        else:
            results["instagram"] = {"success": False, "error": "Skipped"}
            
    def run_tk():
        if config.get("tiktok_enabled"):
            results["tiktok"] = upload_to_tiktok(
                video_path, title, desc, tags,
                config.get("tiktok_session_id")
            )
        else:
            results["tiktok"] = {"success": False, "error": "Skipped"}
            
    for target in [run_yt, run_ig, run_tk]:
        t = threading.Thread(target=target)
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    if results_callback:
        results_callback(results)
    
    return results
