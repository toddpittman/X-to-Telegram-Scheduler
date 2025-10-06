# app.py - COMPLETE VERSION WITH FFMPEG SUPPORT
import streamlit as st
import requests
import json
import re
import os
import tempfile
from datetime import datetime, timedelta
import time
import subprocess

st.set_page_config(
    page_title="X to Telegram Scheduler",
    page_icon="⏰",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    [data-testid="stAppViewContainer"] {
        background-color: #0e1117;
        color: #fafafa;
    }
    [data-testid="stSidebar"] {
        background-color: #262730;
    }
    .stTextInput > div > div > input {
        background-color: #262730;
        color: #fafafa;
        font-size: 16px;
        border: 1px solid #4a4a4a;
    }
    .stTextArea > div > div > textarea {
        background-color: #262730;
        color: #fafafa;
        font-size: 16px;
        border: 1px solid #4a4a4a;
    }
    .stSelectbox > div > div > select {
        background-color: #262730;
        color: #fafafa;
        font-size: 16px;
    }
    .stButton>button {
        width: 100%;
        margin: 5px 0;
        min-height: 44px;
        font-weight: 600;
        color: #ffffff !important;
        background-color: #262730 !important;
        border: 1px solid #4a4a4a !important;
    }
    .stButton>button:hover {
        background-color: #3a3a4a !important;
        border-color: #6a6a8a !important;
    }
    .stButton>button[kind="primary"] {
        background-color: #ff4b4b !important;
        border-color: #ff4b4b !important;
    }
    .stButton>button[kind="primary"]:hover {
        background-color: #ff6b6b !important;
    }
    .stButton>button[kind="secondary"] {
        background-color: #4a4a5a !important;
        border-color: #6a6a7a !important;
    }
    /* Sidebar buttons - FORCE visible text */
    [data-testid="stSidebar"] button {
        color: #ffffff !important;
        background-color: #3a3a4a !important;
        border: 1px solid #5a5a6a !important;
    }
    [data-testid="stSidebar"] button:hover {
        background-color: #4a4a5a !important;
        border-color: #7a7a8a !important;
    }
    [data-testid="stSidebar"] button[kind="primary"] {
        background-color: #ff4b4b !important;
        border-color: #ff4b4b !important;
        color: #ffffff !important;
    }
    [data-testid="stSidebar"] button[kind="secondary"] {
        background-color: #4a4a5a !important;
        border-color: #6a6a7a !important;
        color: #ffffff !important;
    }
    /* Force ALL button text to be white */
    button p, button span, button div {
        color: #ffffff !important;
    }
    /* Fix for info/success/warning/error boxes - READABLE TEXT */
    .stAlert {
        background-color: #1e3a5f !important;
        color: #ffffff !important;
    }
    .stSuccess {
        background-color: #1e4d2b !important;
        color: #ffffff !important;
    }
    .stWarning {
        background-color: #5d4a1f !important;
        color: #ffffff !important;
    }
    .stError {
        background-color: #5d1f1f !important;
        color: #ffffff !important;
    }
    /* Make sure all text in these boxes is white */
    div[data-testid="stMarkdownContainer"] p {
        color: #fafafa !important;
    }
    h1, h2, h3, h4, h5, h6 {
        color: #fafafa !important;
    }
    label, .stMarkdown {
        color: #fafafa !important;
    }
    /* Expandable sections */
    .streamlit-expanderHeader {
        background-color: #262730 !important;
        color: #fafafa !important;
    }
    /* Caption text */
    .caption, small {
        color: #b0b0b0 !important;
    }
    @media (max-width: 640px) {
        .stApp {
            padding: 10px;
        }
        .main .block-container {
            padding: 1rem 0.5rem;
        }
    }
</style>
""", unsafe_allow_html=True)

class SecureXTelegramScheduler:
    def __init__(self):
        self.channels_file = "channels_data.json"
        self.config = self.get_config()
        self.load_channels()
        self.check_team_access()
        
    def load_channels(self):
        try:
            if os.path.exists(self.channels_file):
                with open(self.channels_file, 'r') as f:
                    data = json.load(f)
                    st.session_state.channels = data.get('channels', {})
                    st.session_state.channel_links = data.get('channel_links', {})
            else:
                if 'channels' not in st.session_state:
                    st.session_state.channels = {}
                if 'channel_links' not in st.session_state:
                    st.session_state.channel_links = {}
        except:
            st.session_state.channels = {}
            st.session_state.channel_links = {}
    
    def save_channels(self):
        try:
            data = {
                'channels': st.session_state.channels,
                'channel_links': st.session_state.channel_links
            }
            with open(self.channels_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            st.error(f"Could not save: {str(e)}")
        
    def get_config(self):
        try:
            secrets = st.secrets if hasattr(st, 'secrets') and st.secrets else {}
            
            if hasattr(st.secrets, 'api'):
                api_secrets = st.secrets.api
                x_token = api_secrets.get("x_bearer_token")
                tg_token = api_secrets.get("telegram_bot_token") 
                app_pass = api_secrets.get("app_password")
                team_pass = api_secrets.get("team_passwords", {})
            else:
                x_token = st.secrets.get("x_bearer_token")
                tg_token = st.secrets.get("telegram_bot_token")
                app_pass = st.secrets.get("app_password")
                team_pass = st.secrets.get("team_passwords", {})
            
            return {
                "X_BEARER_TOKEN": x_token or os.getenv("X_BEARER_TOKEN"),
                "TELEGRAM_BOT_TOKEN": tg_token or os.getenv("TELEGRAM_BOT_TOKEN"),
                "APP_PASSWORD": app_pass or os.getenv("APP_PASSWORD"),
                "TEAM_PASSWORDS": team_pass if isinstance(team_pass, dict) else {}
            }
        except Exception as e:
            st.error(f"Config error: {e}")
            st.stop()
    
    def check_team_access(self):
        if "user_authenticated" not in st.session_state:
            st.session_state.user_authenticated = False
            st.session_state.current_user = None
        
        if not st.session_state.user_authenticated:
            st.title("Team Access Required")
            st.markdown("---")
            
            col1, col2 = st.columns(2)
            
            with col1:
                username = st.text_input("Team Member", placeholder="Admin")
            with col2:
                password = st.text_input("Password", type="password", placeholder="Enter password")
            
            if st.button("Login", type="primary", use_container_width=True):
                if username.lower() == "admin" and password == self.config["APP_PASSWORD"]:
                    st.session_state.user_authenticated = True
                    st.session_state.current_user = "Admin"
                    st.success(f"Welcome, {username}!")
                    time.sleep(1)
                    st.rerun()
                elif username in self.config["TEAM_PASSWORDS"] and password == self.config["TEAM_PASSWORDS"][username]:
                    st.session_state.user_authenticated = True
                    st.session_state.current_user = username
                    st.success(f"Welcome, {username}!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Invalid credentials")
            
            st.stop()
        
        if st.sidebar.button("Logout", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    
    def extract_tweet_id(self, url):
        if not url:
            return None
        clean_url = re.sub(r'\?.*$', '', url)
        match = re.search(r'/status/(\d+)', clean_url)
        return match.group(1) if match else None
    
    def fetch_tweet(self, tweet_id):
        if not tweet_id or not self.config['X_BEARER_TOKEN']:
            st.error("Missing tweet ID or token")
            return None
        
        # Debug: Show what we're sending
        st.write(f"**Debug Info:**")
        st.write(f"Tweet ID: `{tweet_id}`")
        st.write(f"Token exists: {bool(self.config['X_BEARER_TOKEN'])}")
        st.write(f"Token preview: `{self.config['X_BEARER_TOKEN'][:20]}...`")
        
        headers = {"Authorization": f"Bearer {self.config['X_BEARER_TOKEN']}"}
        params = {
            "expansions": "attachments.media_keys,author_id",
            "tweet.fields": "attachments,author_id,text,created_at,entities",
            "media.fields": "type,url,variants,preview_image_url",
            "user.fields": "name,username",
            "max_results": 100  # Get full text for long tweets
        }
        
        url = f"https://api.twitter.com/2/tweets/{tweet_id}"
        
        st.write(f"API URL: `{url}`")
        
        try:
            with st.spinner("Fetching tweet..."):
                response = requests.get(url, headers=headers, params=params, timeout=30)
            
            st.write(f"**Response Status:** {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                if "data" not in data:
                    st.error("Invalid response")
                    with st.expander("Debug: API Response"):
                        st.json(data)
                    return None
                
                tweet_data = data["data"]
                if isinstance(tweet_data, list):
                    if len(tweet_data) == 0:
                        return None
                    data["data"] = tweet_data[0]
                
                st.success("Tweet fetched successfully!")
                
                # Process text to expand URLs if entities are present
                tweet_obj = data["data"]
                if "entities" in tweet_obj and "urls" in tweet_obj["entities"]:
                    text = tweet_obj["text"]
                    urls = tweet_obj["entities"]["urls"]
                    
                    # Replace t.co links with display URLs or expanded URLs
                    for url_entity in reversed(urls):  # Reverse to maintain indices
                        t_co_url = url_entity["url"]
                        # Use display_url or expanded_url if available
                        replacement = url_entity.get("display_url", url_entity.get("expanded_url", t_co_url))
                        text = text.replace(t_co_url, replacement)
                    
                    # Update the tweet text with expanded URLs
                    data["data"]["text"] = text
                
                return data
            elif response.status_code == 401:
                st.error("Invalid X Bearer Token - Token is expired or incorrect")
                st.write("Your X_BEARER_TOKEN needs to be updated in Render environment variables")
            elif response.status_code == 404:
                st.error("Tweet not found - Check the URL is correct")
            elif response.status_code == 400:
                st.error("Bad Request - Invalid tweet URL or parameters")
                st.write(f"Tweet ID extracted: {tweet_id}")
                st.write("Make sure you're using the full X URL including the complete status ID")
                with st.expander("Debug: Full API Response"):
                    st.code(response.text)
            else:
                st.error(f"API Error {response.status_code}")
                with st.expander("Debug: Response Details"):
                    st.code(response.text)
            return None
        except Exception as e:
            st.error(f"Error: {str(e)}")
            return None
    
    def download_media_batch(self, media_list, tweet_id):
        if not media_list:
            return []
        
        downloaded = []
        total_size = 0
        
        st.write(f"Downloading {len(media_list)} media items...")
        progress_bar = st.progress(0)
        
        for i, media in enumerate(media_list[:10]):
            try:
                progress_bar.progress((i + 1) / min(len(media_list), 10))
                
                media_type = media.get("type", "unknown")
                st.write(f"**Processing item {i+1}: {media_type}**")
                
                if media_type == "photo":
                    response = requests.get(media["url"], timeout=30, stream=True)
                    response.raise_for_status()
                    
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
                    for chunk in response.iter_content(8192):
                        temp_file.write(chunk)
                    temp_file.close()
                    
                    file_size = os.path.getsize(temp_file.name)
                    if file_size > 10 * 1024 * 1024:
                        os.unlink(temp_file.name)
                        st.warning(f"Photo {i+1} too large, skipped")
                        continue
                    
                    downloaded.append({
                        "type": "photo",
                        "file": temp_file.name,
                        "media_key": media.get("media_key", f"photo_{i}")
                    })
                    total_size += file_size
                    st.success(f"Photo {i+1} downloaded ({file_size/1024/1024:.1f}MB)")
                    
                elif media_type in ["video", "animated_gif"]:
                    # Handle both regular videos and animated GIFs (which Twitter treats as MP4s)
                    st.write(f"**Processing {'GIF' if media_type == 'animated_gif' else 'video'} {i+1}...**")
                    # Twitter API uses 'bit_rate' not 'bitrate'
                    variants = [v for v in media.get("variants", []) if v.get("bit_rate") or v.get("bitrate")]
                    
                    if not variants:
                        st.warning(f"{'GIF' if media_type == 'animated_gif' else 'Video'} {i+1} has no valid variants")
                        st.write(f"Available variants: {media.get('variants', [])}")
                        continue
                    
                    st.write(f"Found {len(variants)} quality options")
                    
                    # Sort by bitrate, highest first (handle both 'bit_rate' and 'bitrate')
                    variants_sorted = sorted(variants, key=lambda x: x.get("bit_rate", x.get("bitrate", 0)), reverse=True)
                    
                    video_downloaded = False
                    for variant_index, variant in enumerate(variants_sorted):
                        try:
                            # Handle both 'bit_rate' and 'bitrate' keys
                            bitrate_value = variant.get('bit_rate', variant.get('bitrate', 0))
                            bitrate_mbps = bitrate_value / 1000000
                            st.info(f"Attempting quality {variant_index + 1}/{len(variants_sorted)}: {bitrate_mbps:.1f} Mbps")
                            st.write(f"URL: {variant['url'][:100]}...")
                            
                            response = requests.get(variant["url"], stream=True, timeout=60)
                            response.raise_for_status()
                            
                            st.write(f"Download started...")
                            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
                            downloaded_size = 0
                            chunks_count = 0
                            
                            for chunk in response.iter_content(8192):
                                if not chunk:
                                    break
                                temp_file.write(chunk)
                                downloaded_size += len(chunk)
                                chunks_count += 1
                                
                                # Progress update every 100 chunks
                                if chunks_count % 100 == 0:
                                    st.write(f"Downloaded: {downloaded_size/1024/1024:.1f}MB...")
                                
                                # Stop if exceeds 50MB
                                if downloaded_size > 50 * 1024 * 1024:
                                    st.warning("Stopping download - exceeds 50MB limit")
                                    break
                            
                            temp_file.close()
                            file_size = os.path.getsize(temp_file.name)
                            
                            st.write(f"**Download complete: {file_size/1024/1024:.1f}MB**")
                            
                            if file_size <= 50 * 1024 * 1024 and file_size > 100000:  # At least 100KB
                                downloaded.append({
                                    "type": "video",  # Telegram treats both as video
                                    "file": temp_file.name,
                                    "media_key": media.get("media_key", f"video_{i}")
                                })
                                total_size += file_size
                                st.success(f"✓ {'GIF' if media_type == 'animated_gif' else 'Video'} {i+1} ready ({file_size/1024/1024:.1f}MB)")
                                video_downloaded = True
                                break
                            elif file_size <= 100000:
                                os.unlink(temp_file.name)
                                st.error(f"File too small ({file_size} bytes) - might be corrupted")
                            else:
                                os.unlink(temp_file.name)
                                st.warning(f"File too large ({file_size/1024/1024:.1f}MB), trying lower quality...")
                                continue
                                
                        except Exception as variant_error:
                            if 'temp_file' in locals() and os.path.exists(temp_file.name):
                                os.unlink(temp_file.name)
                            st.error(f"Quality {variant_index + 1} failed: {str(variant_error)}")
                            continue
                    
                    if not video_downloaded:
                        st.error(f"❌ Could not download {'GIF' if media_type == 'animated_gif' else 'video'} {i+1} - all qualities failed")
                else:
                    st.warning(f"Unknown media type: {media_type} - skipping")
                        
            except Exception as e:
                st.warning(f"Media {i+1} failed: {str(e)}")
                continue
        
        progress_bar.progress(1.0)
        st.info(f"Downloaded {len(downloaded)} items ({total_size/1024/1024:.1f}MB total)")
        return downloaded
    
    def post_media_group(self, chat_id, text, media_list):
        if not self.config['TELEGRAM_BOT_TOKEN']:
            st.error("No Telegram token configured")
            return False, None
        
        url = f"https://api.telegram.org/bot{self.config['TELEGRAM_BOT_TOKEN']}/sendMediaGroup"
        
        try:
            files = []
            media_group = []
            
            for i, media in enumerate(media_list):
                file_handle = open(media["file"], "rb")
                files.append(file_handle)
                
                media_item = {
                    "type": media["type"],
                    "media": f"attach://file{i}"
                }
                if i == 0:
                    media_item["caption"] = text
                media_group.append(media_item)
            
            multipart_data = {
                "chat_id": (None, str(chat_id)),
                "media": (None, json.dumps(media_group))
            }
            
            for i, file_handle in enumerate(files):
                filename = f"file{i}.mp4" if media_list[i]["type"] == "video" else f"file{i}.jpg"
                multipart_data[f"file{i}"] = (filename, file_handle)
            
            with st.spinner("Posting to Telegram..."):
                response = requests.post(url, files=multipart_data, timeout=120)
            
            for file_handle in files:
                file_handle.close()
            
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    self.cleanup_media(media_list)
                    st.success("Posted successfully!")
                    return True, result["result"][0]["message_id"]
                else:
                    st.error(f"Telegram error: {result.get('description')}")
            else:
                st.error(f"HTTP Error {response.status_code}: {response.text}")
        except Exception as e:
            st.error(f"Post failed: {str(e)}")
        
        self.cleanup_media(media_list)
        return False, None
    
    def post_text(self, chat_id, text):
        if not self.config['TELEGRAM_BOT_TOKEN']:
            return False, None
        
        url = f"https://api.telegram.org/bot{self.config['TELEGRAM_BOT_TOKEN']}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": text[:4096],
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        
        try:
            with st.spinner("Posting to Telegram..."):
                response = requests.post(url, data=data, timeout=30)
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    st.success("Posted successfully!")
                    return True, result["result"]["message_id"]
                else:
                    st.error(f"Telegram error: {result.get('description')}")
            else:
                st.error(f"HTTP Error {response.status_code}")
        except Exception as e:
            st.error(f"Post failed: {str(e)}")
        return False, None
    
    def delete_post(self, chat_id, message_id):
        if not self.config['TELEGRAM_BOT_TOKEN']:
            return False
        url = f"https://api.telegram.org/bot{self.config['TELEGRAM_BOT_TOKEN']}/deleteMessage"
        try:
            response = requests.post(url, data={"chat_id": chat_id, "message_id": message_id}, timeout=10)
            return response.json().get("ok", False)
        except:
            return False
    
    def cleanup_media(self, media_list):
        for media in media_list:
            try:
                if os.path.exists(media["file"]):
                    os.unlink(media["file"])
            except:
                pass
    
    def format_channel_id(self, channel_input):
        if not channel_input:
            return None
        channel_input = channel_input.strip()
        if channel_input.startswith("@") or channel_input.startswith("-"):
            return channel_input
        elif channel_input.isdigit():
            if len(channel_input) == 10 and channel_input[0] in ['6', '7', '8', '9']:
                return channel_input
            else:
                return f"-100{channel_input}"
        else:
            return f"@{channel_input}"
    
    def get_video_dimensions(self, video_path):
        """Get video dimensions using FFprobe (part of FFmpeg)"""
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height',
                '-of', 'json',
                video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                if 'streams' in data and len(data['streams']) > 0:
                    width = data['streams'][0].get('width', 0)
                    height = data['streams'][0].get('height', 0)
                    return width, height
        except Exception as e:
            st.warning(f"Could not read video dimensions: {str(e)}")
        return None, None
    
    def post_now(self, chat_id, content_data):
        text = content_data["text"]
        media_list = content_data.get("media", [])
        if media_list:
            return self.post_media_group(chat_id, text, media_list)
        else:
            return self.post_text(chat_id, text)
    
    def run(self):
        st.title("X to Telegram Scheduler")
        st.markdown(f"**Logged in as:** {st.session_state.current_user}")
        st.markdown("---")
        
        with st.sidebar:
            st.header("Channel Manager")
            
            # Check if we're editing a channel
            if "editing_channel" in st.session_state:
                st.subheader(f"Edit: {st.session_state.editing_channel}")
                
                old_name = st.session_state.editing_channel
                old_cid = st.session_state.channels[old_name]
                old_link = st.session_state.channel_links.get(old_name, "")
                
                new_name = st.text_input("Name", value=old_name, key="edit_name")
                new_cid = st.text_input("ID", value=old_cid, key="edit_cid")
                new_link = st.text_input("Custom Link", value=old_link, key="edit_link")
                
                col_save, col_cancel = st.columns(2)
                with col_save:
                    if st.button("Save Changes", type="primary", use_container_width=True):
                        # Delete old entry if name changed
                        if new_name != old_name:
                            del st.session_state.channels[old_name]
                            if old_name in st.session_state.channel_links:
                                del st.session_state.channel_links[old_name]
                        
                        # Save new values
                        st.session_state.channels[new_name] = self.format_channel_id(new_cid)
                        st.session_state.channel_links[new_name] = new_link if new_link else ""
                        self.save_channels()
                        
                        # Update selected channel if it was the one being edited
                        if "selected_channel" in st.session_state and st.session_state.channel_name == old_name:
                            st.session_state.selected_channel = self.format_channel_id(new_cid)
                            st.session_state.channel_name = new_name
                        
                        del st.session_state.editing_channel
                        st.success(f"Updated {new_name}")
                        time.sleep(0.5)
                        st.rerun()
                
                with col_cancel:
                    if st.button("Cancel", type="secondary", use_container_width=True):
                        del st.session_state.editing_channel
                        st.rerun()
                
                # Delete option
                st.markdown("---")
                if st.button("Delete Channel", type="secondary", use_container_width=True):
                    del st.session_state.channels[old_name]
                    if old_name in st.session_state.channel_links:
                        del st.session_state.channel_links[old_name]
                    self.save_channels()
                    
                    # Clear selection if deleted channel was selected
                    if "selected_channel" in st.session_state and st.session_state.channel_name == old_name:
                        del st.session_state.selected_channel
                        del st.session_state.channel_name
                    
                    del st.session_state.editing_channel
                    st.success(f"Deleted {old_name}")
                    time.sleep(0.5)
                    st.rerun()
                
                st.markdown("---")
            else:
                # Normal "Add Channel" form
                st.subheader("Add Channel")
            
            name = st.text_input("Name", key="ch_name", placeholder="My Channel")
            cid = st.text_input("ID", key="ch_id", placeholder="-100123456789")
            link = st.text_input("Custom Link", key="ch_link", placeholder="https://t.me/channel")
            
            if st.button("Save", use_container_width=True) and name and cid:
                st.session_state.channels[name] = self.format_channel_id(cid)
                st.session_state.channel_links[name] = link if link else ""
                self.save_channels()
                st.success(f"Saved {name}")
                time.sleep(0.5)
                st.rerun()
            
            st.markdown("---")
            st.subheader("Your Channels")
            
            # Add search/filter for channels
            if len(st.session_state.channels) > 5:
                search_channel = st.text_input("🔍 Search channels", placeholder="Type to filter...", key="search_ch")
            else:
                search_channel = ""
            
            if st.session_state.channels:
                # Filter channels based on search
                filtered_channels = {
                    name: cid for name, cid in st.session_state.channels.items()
                    if search_channel.lower() in name.lower()
                } if search_channel else st.session_state.channels
                
                if not filtered_channels and search_channel:
                    st.info(f"No channels match '{search_channel}'")
                
                for name, cid in filtered_channels.items():
                    # Compact single-line display per channel
                    st.write(f"**{name}**")
                    st.caption(f"{cid[:25]}...")
                    
                    # Buttons with unique keys
                    select_clicked = st.button("✓ Select", key=f"select_btn_{name}", help=f"Select {name}", use_container_width=True)
                    if select_clicked:
                        st.session_state.selected_channel = cid
                        st.session_state.channel_name = name
                        st.rerun()
                    
                    edit_clicked = st.button("✏️ Edit", key=f"edit_btn_{name}", help=f"Edit {name}", use_container_width=True)
                    if edit_clicked:
                        st.session_state.editing_channel = name
                        st.rerun()
                    
                    # Show link if exists
                    if st.session_state.channel_links.get(name):
                        st.caption(f"🔗 {st.session_state.channel_links[name][:30]}...")
                    
                    st.markdown("---")
            else:
                st.info("No channels yet")
            
            if "selected_channel" in st.session_state:
                st.success(f"Selected: {st.session_state.channel_name}")
        
        tab1, tab2 = st.tabs(["New Post", "Activity"])
        
        with tab1:
            st.header("Create Post")
            
            # Show selected channel prominently at the top
            if "selected_channel" in st.session_state:
                st.success(f"📢 Posting to: **{st.session_state.channel_name}** ({st.session_state.selected_channel})")
            else:
                st.warning("⚠️ No channel selected - Please select a channel from the sidebar")
            
            st.markdown("---")
            
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.subheader("Step 1: Analyze Tweet")
                x_url = st.text_input("Paste X URL", placeholder="https://x.com/user/status/123456789")
                
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    analyze_btn = st.button("Analyze", type="primary", use_container_width=True)
                with col_btn2:
                    cancel_btn = st.button("Cancel", type="secondary", use_container_width=True)
                
                if cancel_btn:
                    # Clear all tweet data
                    for key in ["tweet_data", "original_text", "tweet_url"]:
                        if key in st.session_state:
                            del st.session_state[key]
                    st.success("Cancelled - form cleared")
                    time.sleep(0.5)
                    st.rerun()
                
                if analyze_btn:
                    tweet_id = self.extract_tweet_id(x_url)
                    if tweet_id:
                        tweet_data = self.fetch_tweet(tweet_id)
                        if tweet_data:
                            st.session_state.tweet_data = tweet_data
                            st.session_state.original_text = tweet_data["data"].get("text", "")
                            st.session_state.tweet_url = x_url
                            st.rerun()
                    else:
                        st.error("Invalid URL format")
            
            with col2:
                if "tweet_data" in st.session_state:
                    st.subheader("Tweet Preview")
                    tweet = st.session_state.tweet_data["data"]
                    
                    if "includes" in st.session_state.tweet_data and "users" in st.session_state.tweet_data["includes"]:
                        user = next((u for u in st.session_state.tweet_data["includes"]["users"] 
                                   if u["id"] == tweet["author_id"]), None)
                        if user:
                            st.markdown(f"**{user['name']}** @{user['username']}")
                    
                    st.text_area("Original Text", st.session_state.original_text, height=100, disabled=True)
                    
                    # Debug: Show raw API text
                    if st.checkbox("Show raw API text for debugging"):
                        st.code(st.session_state.tweet_data["data"].get("text", "No text"))
                    
                    if "includes" in st.session_state.tweet_data and "media" in st.session_state.tweet_data["includes"]:
                        media_list = st.session_state.tweet_data["includes"]["media"]
                        st.info(f"Media: {len(media_list)} items")
                        
                        cols = st.columns(min(3, len(media_list)))
                        for i, media in enumerate(media_list[:3]):
                            with cols[i]:
                                if media["type"] == "photo":
                                    st.image(media["url"], use_column_width=True)
                                elif media["type"] == "video":
                                    st.write("🎥 Video")
                                    if "preview_image_url" in media:
                                        st.image(media["preview_image_url"], use_column_width=True, caption="Video preview")
                                    # Show video info
                                    variants = media.get("variants", [])
                                    if variants:
                                        st.caption(f"{len(variants)} quality options available")
            
            if "tweet_data" in st.session_state:
                st.markdown("---")
                st.subheader("Step 2: Customize & Post")
                
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    edited_text = st.text_area(
                        "Edit text (4,096 chars max)", 
                        value=st.session_state.original_text, 
                        height=200,
                        key="edit_text_area"
                    )
                    st.caption(f"{len(edited_text)}/4,096 characters")
                    
                    if "selected_channel" in st.session_state:
                        link = st.session_state.channel_links.get(st.session_state.channel_name, "")
                        if link:
                            st.caption(f"Channel link: {link}")
                            if st.checkbox("Add channel link to end of post"):
                                if link not in edited_text:
                                    edited_text = edited_text + f"\n\n{link}"
                
                with col2:
                    st.markdown("**Target Channel:**")
                    if "selected_channel" in st.session_state:
                        st.success(f"{st.session_state.channel_name}")
                        st.caption(f"ID: {st.session_state.selected_channel}")
                    else:
                        st.warning("No channel selected")
                
                # Always remove X/Twitter links and t.co shortened links automatically
                cleaned_text = re.sub(r'https?://(twitter\.com|x\.com|t\.co)/\S+', '', edited_text)
                final_text = cleaned_text.strip()[:4096]
                
                with st.expander("Final Preview", expanded=True):
                    st.markdown("**Text that will be posted:**")
                    st.write(final_text)
                    if "includes" in st.session_state.tweet_data and "media" in st.session_state.tweet_data["includes"]:
                        media_count = len(st.session_state.tweet_data["includes"]["media"])
                        st.info(f"**{media_count}** media items will be attached")
                
                if "selected_channel" in st.session_state:
                    if st.button("POST TO TELEGRAM", type="primary", use_container_width=True):
                        st.write("=" * 50)
                        st.write("**STARTING POST PROCESS**")
                        st.write("=" * 50)
                        
                        with st.spinner("Processing..."):
                            media_data = []
                            
                            # Check if there's media to download
                            if "includes" in st.session_state.tweet_data and "media" in st.session_state.tweet_data["includes"]:
                                st.write(f"**Found {len(st.session_state.tweet_data['includes']['media'])} media items in tweet**")
                                
                                for idx, media in enumerate(st.session_state.tweet_data["includes"]["media"]):
                                    st.write(f"Media {idx+1} type: {media.get('type', 'unknown')}")
                                
                                media_data = self.download_media_batch(
                                    st.session_state.tweet_data["includes"]["media"],
                                    st.session_state.tweet_data["data"]["id"]
                                )
                                
                                st.write(f"**Download complete: {len(media_data)} items ready**")
                            else:
                                st.write("**No media to download - text only post**")
                            
                            content_data = {
                                "text": final_text,
                                "media": media_data,
                                "channel_name": st.session_state.channel_name
                            }
                            
                            st.write("**Attempting to post...**")
                            success, message_id = self.post_now(st.session_state.selected_channel, content_data)
                            
                            st.write("=" * 50)
                            if success:
                                st.write("**POST COMPLETED SUCCESSFULLY**")
                                if "activity_log" not in st.session_state:
                                    st.session_state.activity_log = []
                                st.session_state.activity_log.append({
                                    "user": st.session_state.current_user,
                                    "channel": st.session_state.channel_name,
                                    "time": datetime.now(),
                                    "preview": final_text[:50],
                                    "media_count": len(media_data),
                                    "message_id": message_id
                                })
                                
                                del st.session_state.tweet_data
                                del st.session_state.original_text
                                if "tweet_url" in st.session_state:
                                    del st.session_state.tweet_url
                                
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.write("**POST FAILED - SEE ERRORS ABOVE**")
                else:
                    st.warning("Please select a channel first")
        
        with tab2:
            st.header("Activity Log")
            
            if "activity_log" in st.session_state and st.session_state.activity_log:
                st.info(f"**Total posts:** {len(st.session_state.activity_log)}")
                
                for activity in reversed(st.session_state.activity_log[-20:]):
                    with st.container():
                        col1, col2, col3, col4 = st.columns([2, 3, 1, 1])
                        
                        with col1:
                            st.write(f"**{activity['channel']}**")
                            st.caption(f"{activity['user']}")
                        
                        with col2:
                            st.write(f"{activity['preview']}...")
                            if activity.get('media_count', 0) > 0:
                                st.caption(f"{activity['media_count']} media items")
                        
                        with col3:
                            st.write(f"{activity['time'].strftime('%H:%M')}")
                        
                        with col4:
                            if activity.get('message_id') and "selected_channel" in st.session_state:
                                if st.button("Delete", key=f"del_{activity['message_id']}", help="Delete post"):
                                    if self.delete_post(st.session_state.selected_channel, activity['message_id']):
                                        st.success("Deleted!")
                                        time.sleep(0.5)
                                        st.rerun()
                        
                        st.markdown("---")
                
                col_clear1, col_clear2 = st.columns([3, 1])
                with col_clear2:
                    if st.button("Clear Log", type="secondary", use_container_width=True):
                        st.session_state.activity_log = []
                        st.rerun()
            else:
                st.info("No activity yet")

if __name__ == "__main__":
    try:
        app = SecureXTelegramScheduler()
        app.run()
    except Exception as e:
        st.error(f"App error: {str(e)}")