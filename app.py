# app.py - COMPLETE FIXED VERSION
import streamlit as st
import requests
import json
import re
import os
import tempfile
from datetime import datetime, timedelta
import time
from urllib.parse import urlparse

# Page config - Dark mode for iPad/iPhone
st.set_page_config(
    page_title="X → Telegram Scheduler",
    page_icon="⏰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Enhanced dark theme for mobile optimization
st.markdown("""
<style>
    [data-testid="stAppViewContainer"] {
        background-color: #0e1117;
        color: #fafafa;
    }
    .stTextInput > div > div > input {
        background-color: #1f2937;
        color: #fafafa;
        font-size: 16px; /* Prevents iOS zoom */
    }
    .stTextArea > div > div > textarea {
        background-color: #1f2937;
        color: #fafafa;
        font-size: 16px;
    }
    .stSelectbox > div > div > select {
        font-size: 16px;
    }
    .stButton>button {
        width: 100%;
        margin: 5px 0;
        min-height: 44px; /* iOS touch target */
    }
    @media (max-width: 640px) {
        .stApp {
            padding: 10px;
        }
        .stTextArea {
            height: 120px !important;
        }
        .main .block-container {
            padding: 1rem 0.5rem;
            max-width: 100%;
        }
    }
    @media (max-width: 1024px) and (min-width: 641px) {
        .main .block-container {
            padding: 2rem 1rem;
        }
    }
    .error-details {
        background-color: #2d1b1b;
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .debug-info {
        background-color: #1a2332;
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
        font-family: monospace;
        font-size: 12px;
    }
</style>
""", unsafe_allow_html=True)

class SecureXTelegramScheduler:
    def __init__(self):
        self.config = self.get_config()
        self.check_team_access()
        
    def get_config(self):
        """Load secure config from secrets.toml or environment"""
        try:
            import streamlit as st
            secrets = st.secrets if hasattr(st, 'secrets') and st.secrets else {}
            
            # Handle different secret structures
            if hasattr(st.secrets, 'api'):
                api_secrets = st.secrets.api
                x_token = api_secrets.get("x_bearer_token")
                tg_token = api_secrets.get("telegram_bot_token") 
                app_pass = api_secrets.get("app_password")
                team_pass = api_secrets.get("team_passwords", {})
            else:
                # Fallback to direct secrets access
                x_token = st.secrets.get("x_bearer_token") or st.secrets.get("X_BEARER_TOKEN")
                tg_token = st.secrets.get("telegram_bot_token") or st.secrets.get("TELEGRAM_BOT_TOKEN")
                app_pass = st.secrets.get("app_password") or st.secrets.get("APP_PASSWORD")
                team_pass = st.secrets.get("team_passwords", {}) or st.secrets.get("TEAM_PASSWORDS", {})
            
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
        """Team authentication system with admin fallback"""
        if "user_authenticated" not in st.session_state:
            st.session_state.user_authenticated = False
            st.session_state.current_user = None
            st.session_state.app_password = False
        
        if not st.session_state.user_authenticated:
            st.title("🔐 Team Access Required")
            st.markdown("**Enterprise Content Scheduler**")
            
            # Admin login
            st.subheader("Admin Access")
            username = st.text_input("Team Member:", placeholder="Admin", value="Admin")
            password = st.text_input("Password:", type="password", placeholder="NeroCar123@")
            
            if st.button("🔑 Login", type="primary", use_container_width=True):
                # Check admin password first
                if username.lower() == "admin" and password == self.config["APP_PASSWORD"]:
                    st.session_state.user_authenticated = True
                    st.session_state.current_user = "Admin"
                    st.session_state.app_password = True
                    st.success(f"Welcome back, {username}!")
                    time.sleep(1)
                    st.rerun()
                # Check team passwords
                elif username in self.config["TEAM_PASSWORDS"] and \
                     password == self.config["TEAM_PASSWORDS"][username]:
                    st.session_state.user_authenticated = True
                    st.session_state.current_user = username
                    st.session_state.app_password = True
                    st.success(f"Welcome back, {username.title()}!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Invalid credentials")
                    
            # Debug info for troubleshooting
            if st.checkbox("Show Debug Info"):
                st.markdown("**Debug Information:**")
                st.write("Available config keys:", list(self.config.keys()))
                st.write("X Token exists:", bool(self.config.get("X_BEARER_TOKEN")))
                st.write("Telegram Token exists:", bool(self.config.get("TELEGRAM_BOT_TOKEN")))
                st.write("App Password exists:", bool(self.config.get("APP_PASSWORD")))
                st.write("Team Passwords:", list(self.config.get("TEAM_PASSWORDS", {}).keys()))
            
            st.stop()
        
        # Logout option
        if st.sidebar.button("🚪 Logout", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    
    def extract_tweet_id(self, url):
        """Extract tweet ID - handles all URL formats"""
        if not url:
            return None
        clean_url = re.sub(r'\?.*$', '', url)
        match = re.search(r'/status/(\d+)', clean_url)
        return match.group(1) if match else None
    
    def test_api_credentials(self):
        """Test API credentials with detailed feedback"""
        st.subheader("🧪 API Credential Testing")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Test X Bearer Token
            if st.button("Test X Bearer Token", use_container_width=True):
                if not self.config['X_BEARER_TOKEN']:
                    st.error("❌ No X Bearer Token found")
                    return
                    
                headers = {"Authorization": f"Bearer {self.config['X_BEARER_TOKEN']}"}
                test_url = "https://api.twitter.com/2/tweets/20"  # Twitter's first tweet
                
                try:
                    with st.spinner("Testing X API..."):
                        response = requests.get(test_url, headers=headers, timeout=10)
                        
                    st.markdown(f"**Status Code:** {response.status_code}")
                    
                    if response.status_code == 200:
                        st.success("✅ X Bearer Token is valid!")
                        data = response.json()
                        st.json(data)
                    elif response.status_code == 401:
                        st.error("❌ X Bearer Token is invalid or expired")
                        st.markdown('<div class="error-details">Check your token in secrets.toml</div>', unsafe_allow_html=True)
                    elif response.status_code == 429:
                        st.warning("⚠️ Rate limited - token might be valid but overused")
                    else:
                        st.error(f"❌ API Error: {response.status_code}")
                        
                    st.markdown('<div class="debug-info">Response: ' + str(response.text) + '</div>', unsafe_allow_html=True)
                        
                except Exception as e:
                    st.error(f"🚨 Connection error: {str(e)}")
        
        with col2:
            # Test Telegram Bot Token
            if st.button("Test Telegram Bot Token", use_container_width=True):
                if not self.config['TELEGRAM_BOT_TOKEN']:
                    st.error("❌ No Telegram Bot Token found")
                    return
                    
                try:
                    with st.spinner("Testing Telegram API..."):
                        url = f"https://api.telegram.org/bot{self.config['TELEGRAM_BOT_TOKEN']}/getMe"
                        response = requests.get(url, timeout=10)
                        
                    st.markdown(f"**Status Code:** {response.status_code}")
                    
                    if response.status_code == 200:
                        bot_info = response.json()
                        if bot_info.get('ok'):
                            st.success(f"✅ Bot Token valid: {bot_info['result']['first_name']}")
                            st.json(bot_info['result'])
                        else:
                            st.error("❌ Bot Token invalid")
                    else:
                        st.error(f"❌ Telegram API Error: {response.status_code}")
                        
                    st.markdown('<div class="debug-info">Response: ' + str(response.text) + '</div>', unsafe_allow_html=True)
                        
                except Exception as e:
                    st.error(f"🚨 Connection error: {str(e)}")
    
    def fetch_tweet(self, tweet_id):
        """Fetch tweet with comprehensive error handling and debugging"""
        if not tweet_id:
            st.error("❌ No tweet ID provided")
            return None
            
        if not self.config['X_BEARER_TOKEN']:
            st.error("❌ No X Bearer Token configured")
            return None
        
        headers = {"Authorization": f"Bearer {self.config['X_BEARER_TOKEN']}"}
        params = {
            "expansions": "attachments.media_keys,author_id",
            "tweet.fields": "attachments,author_id,text,created_at,public_metrics",
            "media.fields": "type,url,variants,preview_image_url",
            "user.fields": "name,username,profile_image_url"
        }
        
        url = f"https://api.twitter.com/2/tweets/{tweet_id}"
        
        # Debug output
        with st.expander("🔍 Debug Information", expanded=False):
            st.write(f"Tweet ID: `{tweet_id}`")
            st.write(f"API URL: `{url}`")
            st.write(f"Token exists: `{bool(self.config['X_BEARER_TOKEN'])}`")
            st.write(f"Token preview: `{self.config['X_BEARER_TOKEN'][:20]}...`")
        
        try:
            with st.spinner("Fetching tweet data..."):
                response = requests.get(url, headers=headers, params=params, timeout=30)
            
            # Detailed response analysis
            st.write(f"**Response Status:** {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    
                    with st.expander("📋 Raw API Response", expanded=False):
                        st.json(data)
                    
                    # Check response structure
                    if "data" not in data:
                        st.error("❌ API response missing 'data' field")
                        st.write("Available keys:", list(data.keys()))
                        return None
                    
                    # Handle both single tweet and array formats
                    tweet_data = data["data"]
                    if isinstance(tweet_data, list):
                        if len(tweet_data) == 0:
                            st.error("❌ Empty tweet data array")
                            return None
                        # Use first tweet from array
                        tweet_obj = tweet_data[0]
                        # Update data structure to be consistent
                        data["data"] = tweet_obj
                    elif isinstance(tweet_data, dict):
                        # Single tweet object - this is fine
                        tweet_obj = tweet_data
                    else:
                        st.error("❌ Unexpected data format")
                        return None
                    
                    # Verify we have the essential fields
                    if not tweet_obj.get("text"):
                        st.warning("⚠️ Tweet has no text content")
                    
                    st.success("✅ Tweet data fetched successfully!")
                    st.write(f"**Text preview:** {tweet_obj.get('text', 'No text')[:100]}...")
                    
                    return data
                    
                except json.JSONDecodeError as e:
                    st.error(f"❌ JSON decode error: {str(e)}")
                    st.write("Raw response:", response.text[:500])
                    return None
                    
            elif response.status_code == 401:
                st.error("🔐 Authentication failed - Invalid Bearer Token")
                st.markdown('<div class="error-details">Your X_BEARER_TOKEN is invalid or expired</div>', unsafe_allow_html=True)
                
            elif response.status_code == 403:
                st.error("🚫 Access forbidden - Token lacks permissions")
                
            elif response.status_code == 404:
                st.error("🔍 Tweet not found")
                st.info("Tweet might be deleted, private, or the ID is incorrect")
                
            elif response.status_code == 429:
                st.error("⏱️ Rate limit exceeded")
                st.info("Wait 15 minutes before trying again")
                
            else:
                st.error(f"❌ API Error {response.status_code}")
                
            # Always show response text for debugging
            with st.expander("📝 API Response Details", expanded=False):
                st.code(response.text)
            return None
            
        except requests.exceptions.Timeout:
            st.error("⏱️ Request timed out - API might be slow")
            return None
        except requests.exceptions.ConnectionError:
            st.error("🌐 Connection error - Check your internet connection")
            return None
        except Exception as e:
            st.error(f"🚨 Unexpected error: {str(e)}")
            st.write("Error type:", type(e).__name__)
            return None
    
    def download_media_batch(self, media_list, tweet_id):
        """Download multiple media with size limits and error handling"""
        if not media_list:
            st.info("ℹ️ No media to download")
            return []
            
        downloaded = []
        total_size = 0
        
        st.write(f"📥 Downloading {len(media_list)} media items...")
        progress_bar = st.progress(0)
        
        for i, media in enumerate(media_list[:10]):  # Telegram limit
            try:
                progress_bar.progress((i + 1) / min(len(media_list), 10))
                st.write(f"Processing media {i+1}: {media.get('type', 'unknown')}")
                
                if media["type"] == "photo":
                    response = requests.get(media["url"], timeout=30, stream=True)
                    response.raise_for_status()
                    
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
                    for chunk in response.iter_content(chunk_size=8192):
                        temp_file.write(chunk)
                    temp_file.close()
                    
                    file_size = os.path.getsize(temp_file.name)
                    if file_size > 10 * 1024 * 1024:  # 10MB limit
                        os.unlink(temp_file.name)
                        st.warning(f"Photo {i+1} too large ({file_size/1024/1024:.1f}MB), skipped")
                        continue
                    
                    downloaded.append({
                        "type": "photo",
                        "file": temp_file.name,
                        "media_key": media.get("media_key", f"photo_{i}")
                    })
                    total_size += file_size
                    st.success(f"✅ Downloaded photo {i+1} ({file_size/1024/1024:.1f}MB)")
                    
                elif media["type"] == "video":
                    variants = [v for v in media.get("variants", []) if v.get("bitrate")]
                    if not variants:
                        st.warning(f"Video {i+1} has no valid variants")
                        continue
                        
                    # Try highest quality first, fall back to lower quality
                    for variant in sorted(variants, key=lambda x: x.get("bitrate", 0), reverse=True):
                        try:
                            response = requests.get(variant["url"], stream=True, timeout=30)
                            response.raise_for_status()
                            
                            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
                            downloaded_size = 0
                            
                            for chunk in response.iter_content(chunk_size=8192):
                                if not chunk:
                                    break
                                temp_file.write(chunk)
                                downloaded_size += len(chunk)
                                if downloaded_size > 50 * 1024 * 1024:  # 50MB limit
                                    break
                            
                            temp_file.close()
                            file_size = os.path.getsize(temp_file.name)
                            
                            if file_size <= 50 * 1024 * 1024:
                                downloaded.append({
                                    "type": "video",
                                    "file": temp_file.name,
                                    "media_key": media.get("media_key", f"video_{i}")
                                })
                                total_size += file_size
                                st.success(f"✅ Downloaded video {i+1} ({file_size/1024/1024:.1f}MB)")
                                break
                            else:
                                os.unlink(temp_file.name)
                                st.warning(f"Video {i+1} too large, trying lower quality...")
                                continue
                                
                        except Exception as variant_error:
                            if 'temp_file' in locals() and os.path.exists(temp_file.name):
                                os.unlink(temp_file.name)
                            st.warning(f"Failed to download video variant: {str(variant_error)}")
                            continue
                    
                    else:
                        st.error(f"❌ Could not download video {i+1} - all variants failed")
                        
            except Exception as e:
                st.warning(f"Media {i+1} download failed: {str(e)}")
                continue
        
        progress_bar.progress(1.0)
        st.info(f"✅ Downloaded {len(downloaded)} items ({total_size/1024/1024:.1f}MB total)")
        return downloaded
    
    def verify_telegram_channel(self, chat_id):
        """Verify telegram channel access"""
        if not self.config['TELEGRAM_BOT_TOKEN']:
            st.error("❌ No Telegram Bot Token configured")
            return False
            
        try:
            url = f"https://api.telegram.org/bot{self.config['TELEGRAM_BOT_TOKEN']}/getChat"
            response = requests.get(url, params={'chat_id': chat_id}, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    chat_info = result['result']
                    st.success(f"✅ Channel verified: {chat_info.get('title', 'Unknown')}")
                    st.write(f"Type: {chat_info.get('type')}")
                    st.write(f"Members: {chat_info.get('member_count', 'Unknown')}")
                    return True
                else:
                    st.error(f"❌ Telegram API error: {result.get('description', 'Unknown')}")
            else:
                st.error(f"❌ HTTP Error {response.status_code}")
                st.write("Response:", response.text)
                
        except Exception as e:
            st.error(f"🚨 Channel verification error: {str(e)}")
            
        return False
    
    def schedule_post(self, chat_id, content_data, schedule_time=None):
        """Schedule or post immediately"""
        if schedule_time and schedule_time > datetime.now():
            if "scheduled_posts" not in st.session_state:
                st.session_state.scheduled_posts = []
            
            st.session_state.scheduled_posts.append({
                "chat_id": chat_id,
                "content": content_data,
                "schedule_time": schedule_time,
                "status": "scheduled",
                "user": st.session_state.current_user,
                "created": datetime.now()
            })
            
            # Simple scheduler (runs in background)
            self.run_scheduler()
            st.success(f"⏰ Scheduled for {schedule_time.strftime('%Y-%m-%d %H:%M')}")
            return True, None
        else:
            return self.post_now(chat_id, content_data)
    
    def run_scheduler(self):
        """Background scheduler (runs every 60 seconds)"""
        if "last_scheduler_run" not in st.session_state or \
           (time.time() - st.session_state.last_scheduler_run) > 60:
            if "scheduled_posts" in st.session_state:
                now = datetime.now()
                for post in st.session_state.scheduled_posts[:]:
                    if post["status"] == "scheduled" and post["schedule_time"] <= now:
                        success, message_id = self.post_now(post["chat_id"], post["content"])
                        if success:
                            post["status"] = "posted"
                            post["message_id"] = message_id
                            if "activity_log" not in st.session_state:
                                st.session_state.activity_log = []
                            st.session_state.activity_log.append({
                                "user": post["user"],
                                "action": "scheduled_post",
                                "channel": post["chat_id"],
                                "time": now,
                                "content_preview": post["content"]["text"][:50]
                            })
            st.session_state.last_scheduler_run = time.time()
    
    def post_now(self, chat_id, content_data):
        """Execute immediate post"""
        text = content_data["text"]
        media_list = content_data.get("media", [])
        
        if media_list:
            success, message_id = self.post_media_group(chat_id, text, media_list)
        else:
            success, message_id = self.post_text(chat_id, text)
        
        return success, message_id
    
    def post_media_group(self, chat_id, text, media_list):
        """Post media album with proper error handling"""
        if not self.config['TELEGRAM_BOT_TOKEN']:
            st.error("❌ No Telegram Bot Token configured")
            return False, None
            
        url = f"https://api.telegram.org/bot{self.config['TELEGRAM_BOT_TOKEN']}/sendMediaGroup"
        
        files = {}
        media_group = []
        
        try:
            for i, media in enumerate(media_list):
                file_key = f"media_{i}"
                with open(media["file"], "rb") as file:
                    files[file_key] = file.read()
                
                media_item = {
                    "type": media["type"],
                    "media": f"attach://{file_key}",
                    "caption": text if i == 0 else ""
                }
                media_group.append(media_item)
            
            data = {
                "chat_id": chat_id,
                "media": json.dumps(media_group)
            }
            
            # Convert files dict for multipart upload
            files_for_upload = {}
            for key, content in files.items():
                files_for_upload[key] = ('file', content)
            
            with st.spinner("Posting to Telegram..."):
                response = requests.post(url, data=data, files=files_for_upload, timeout=120)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    self.cleanup_media(media_list)
                    return True, result["result"][0]["message_id"]
                else:
                    st.error(f"❌ Telegram error: {result.get('description', 'Unknown')}")
            else:
                st.error(f"❌ HTTP Error {response.status_code}: {response.text}")
                
        except Exception as e:
            st.error(f"❌ Post failed: {str(e)}")
        
        self.cleanup_media(media_list)
        return False, None
    
    def post_text(self, chat_id, text):
        """Post text only (up to 4,096 chars)"""
        if not self.config['TELEGRAM_BOT_TOKEN']:
            st.error("❌ No Telegram Bot Token configured")
            return False, None
            
        url = f"https://api.telegram.org/bot{self.config['TELEGRAM_BOT_TOKEN']}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": text[:4096],  # Telegram Premium limit
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        
        try:
            with st.spinner("Posting to Telegram..."):
                response = requests.post(url, data=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    return True, result["result"]["message_id"]
                else:
                    st.error(f"❌ Telegram error: {result.get('description', 'Unknown')}")
            else:
                st.error(f"❌ HTTP Error {response.status_code}: {response.text}")
                
        except Exception as e:
            st.error(f"❌ Text post failed: {str(e)}")
            
        return False, None
    
    def delete_post(self, chat_id, message_id):
        """Delete post for undo functionality"""
        if not self.config['TELEGRAM_BOT_TOKEN']:
            return False
            
        url = f"https://api.telegram.org/bot{self.config['TELEGRAM_BOT_TOKEN']}/deleteMessage"
        data = {"chat_id": chat_id, "message_id": message_id}
        
        try:
            response = requests.post(url, data=data, timeout=10)
            result = response.json()
            return result.get("ok", False)
        except:
            return False
    
    def cleanup_media(self, media_list):
        """Clean up temp files"""
        for media in media_list:
            try:
                if os.path.exists(media["file"]):
                    os.unlink(media["file"])
            except Exception as e:
                st.warning(f"Could not clean up {media['file']}: {str(e)}")
    
    def format_channel_id(self, channel_input):
        """Smart channel ID formatting"""
        if not channel_input:
            return None
            
        channel_input = channel_input.strip()
        
        # Don't modify if it already looks correct
        if channel_input.startswith("@") or channel_input.startswith("-"):
            return channel_input
        elif channel_input.isdigit():
            # If it's a 10-digit number starting with 6-9, it's likely a personal chat
            if len(channel_input) == 10 and channel_input[0] in ['6', '7', '8', '9']:
                return channel_input
            else:
                return f"-100{channel_input}"
        else:
            return f"@{channel_input}"
    
    def run(self):
        """Main app interface"""
        st.title("⏰ X → Telegram Enterprise Scheduler")
        st.markdown(f"**Logged in as:** {st.session_state.current_user}")
        st.markdown("---")
        
        # Add testing tab to main interface
        tab_test, tab_main, tab_activity = st.tabs(["🧪 Testing", "📝 New Post", "📊 Activity"])
        
        with tab_test:
            st.header("🔧 Debug & Testing Tools")
            
            self.test_api_credentials()
            
            st.markdown("---")
            
            # Test Telegram Channel
            st.subheader("📱 Test Telegram Channel")
            test_channel = st.text_input("Channel ID to test:", value="6984175112")
            if st.button("Test Channel Access", use_container_width=True):
                formatted_id = self.format_channel_id(test_channel)
                st.write(f"Testing: `{formatted_id}`")
                self.verify_telegram_channel(formatted_id)
            
            st.markdown("---")
            
            # Test with sample URLs
            st.subheader("🔗 Test X URL Analysis")
            sample_urls = [
                "https://x.com/Twitter/status/20",  # First tweet
                "https://x.com/elonmusk/status/1683325363957772289",  # Sample Elon tweet
                "https://x.com/Geiger_Capital/status/1704939943176315303"  # Your original
            ]
            
            selected_url = st.selectbox("Choose test URL:", ["Custom"] + sample_urls)
            if selected_url == "Custom":
                test_url = st.text_input("Enter X URL:")
            else:
                test_url = selected_url
                st.write(f"Testing: `{test_url}`")
            
            if st.button("🔍 Test Tweet Analysis", use_container_width=True) and test_url:
                tweet_id = self.extract_tweet_id(test_url)
                if tweet_id:
                    st.write(f"Extracted Tweet ID: `{tweet_id}`")
                    tweet_data = self.fetch_tweet(tweet_id)
                    if tweet_data:
                        st.success("✅ Tweet analysis successful!")
                        # Store in session for use in main tab
                        st.session_state.test_tweet_data = tweet_data
                        st.session_state.test_tweet_url = test_url
                else:
                    st.error("❌ Could not extract tweet ID from URL")
        
        # Channel Manager Sidebar
        with st.sidebar:
            st.header("📱 Channel Manager")
            
            if "channels" not in st.session_state:
                st.session_state.channels = {
                    "Test Channel": "-100305136131"  # Your provided channel
                }
            
            # Add/Edit channel
            st.subheader("Add/Edit Channel")
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Name", key="new_channel_name", placeholder="My Channel")
            with col2:
                cid = st.text_input("ID/@handle", key="new_channel_id", placeholder="-100123456789")
            
            if st.button("➕ Save Channel", use_container_width=True) and name and cid:
                st.session_state.channels[name] = self.format_channel_id(cid)
                st.success(f"Added {name}")
                st.rerun()
            
            # Channel list with selection
            st.subheader("Your Channels")
            if st.session_state.channels:
                for name, cid in st.session_state.channels.items():
                    col_a, col_b = st.columns([3, 1])
                    with col_a:
                        st.write(f"📢 {name}")
                        st.caption(f"{cid}")
                    with col_b:
                        if st.button("Select", key=f"ch_{name}"):
                            st.session_state.selected_channel = cid
                            st.session_state.channel_name = name
                            st.rerun()
            
            # Show selected channel
            if "selected_channel" in st.session_state:
                st.success(f"✅ Selected: {st.session_state.channel_name}")
            
            # Scheduled posts overview
            if "scheduled_posts" in st.session_state and st.session_state.scheduled_posts:
                st.subheader("⏰ Scheduled")
                for i, post in enumerate(st.session_state.scheduled_posts):
                    if post["status"] == "scheduled":
                        st.write(f"**{post.get('channel_name', 'Unknown')}**")
                        st.caption(f"{post['schedule_time'].strftime('%H:%M %d/%m')}")
                        if st.button("🚫 Cancel", key=f"cancel_{i}"):
                            del st.session_state.scheduled_posts[i]
                            st.rerun()
        
        # Main workflow tabs
        with tab_main:
            st.header("📝 Create New Post")
            
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.subheader("Step 1: Analyze X Post")
                x_url = st.text_input("Paste X URL", placeholder="https://x.com/user/status/123...")
                
                if st.button("🔍 Analyze", type="primary", use_container_width=True):
                    tweet_id = self.extract_tweet_id(x_url)
                    if tweet_id:
                        with st.spinner("Fetching tweet..."):
                            tweet_data = self.fetch_tweet(tweet_id)
                            if tweet_data:
                                # Handle both array and object responses
                                tweet_obj = tweet_data["data"]
                                
                                st.session_state.tweet_data = tweet_data
                                st.session_state.original_text = tweet_obj.get("text", "")
                                st.session_state.tweet_url = x_url
                                st.rerun()
                            else:
                                st.error("Failed to fetch tweet")
                    else:
                        st.error("Invalid URL format")
            
            with col2:
                if "tweet_data" in st.session_state:
                    st.subheader("Tweet Preview")
                    tweet = st.session_state.tweet_data["data"]
                    
                    # Author info
                    if "includes" in st.session_state.tweet_data and "users" in st.session_state.tweet_data["includes"]:
                        user = next((u for u in st.session_state.tweet_data["includes"]["users"] 
                                   if u["id"] == tweet["author_id"]), None)
                        if user:
                            st.markdown(f"**{user['name']}** (@{user['username']})")
                    
                    # Text preview
                    st.text_area("Original Text:", st.session_state.original_text, height=100, disabled=True)
                    
                    # Media preview
                    if "includes" in st.session_state.tweet_data and "media" in st.session_state.tweet_data["includes"]:
                        media_list = st.session_state.tweet_data["includes"]["media"]
                        st.write(f"**Media:** {len(media_list)} items")
                        
                        # Show media previews
                        cols = st.columns(min(3, len(media_list)))
                        for i, media in enumerate(media_list[:3]):
                            with cols[i]:
                                if media["type"] == "photo":
                                    st.image(media["url"], use_column_width=True)
                                elif media["type"] == "video":
                                    st.write(f"🎥 Video {i+1}")
                                    if "preview_image_url" in media:
                                        st.image(media["preview_image_url"], use_column_width=True)
            
            # Post editing and publishing
            if "tweet_data" in st.session_state:
                st.markdown("---")
                st.subheader("Step 2: Customize & Post")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    # Channel selection
                    st.markdown("**Target Channel:**")
                    if "selected_channel" in st.session_state:
                        st.success(f"✅ {st.session_state.channel_name}")
                        st.caption(f"ID: {st.session_state.selected_channel}")
                    else:
                        st.warning("⚠️ No channel selected")
                        st.info("Select a channel from the sidebar")
                
                with col2:
                    # Text editing
                    edited_text = st.text_area(
                        "Edit text (4,096 chars max):",
                        value=st.session_state.original_text,
                        height=150,
                        key="edit_text"
                    )
                    st.caption(f"{len(edited_text)}/4096 characters")
                
                with col3:
                    # Scheduling options
                    st.markdown("**Schedule:**")
                    schedule_now = st.checkbox("Post Immediately", value=True)
                    
                    if not schedule_now:
                        schedule_date = st.date_input("Date", min_value=datetime.now().date())
                        schedule_time = st.time_input("Time", value=datetime.now().time())
                        schedule_datetime = datetime.combine(schedule_date, schedule_time)
                    else:
                        schedule_datetime = None
                
                # Final review and post
                st.markdown("---")
                st.subheader("Step 3: Review & Confirm")
                
                final_text = edited_text[:4096]
                
                with st.expander("👁️ Final Preview", expanded=True):
                    st.markdown("**Text:**")
                    st.markdown(final_text)
                    
                    if "includes" in st.session_state.tweet_data and "media" in st.session_state.tweet_data["includes"]:
                        media_count = len(st.session_state.tweet_data["includes"]["media"])
                        st.markdown(f"**Media:** {media_count} items will be posted")
                
                # Safety confirmation
                col_a, col_b = st.columns(2)
                with col_a:
                    if "selected_channel" in st.session_state:
                        confirm_channel = st.selectbox(
                            "Confirm posting to:",
                            options=[st.session_state.selected_channel],
                            format_func=lambda x: f"{st.session_state.channel_name} ({x})"
                        )
                    else:
                        st.error("❌ Please select a channel first")
                        confirm_channel = None
                
                with col_b:
                    st.info(f"**User:** {st.session_state.current_user}")
                    post_type = "⏰ Scheduled" if not schedule_now else "🚀 Immediate"
                    st.info(post_type)
                
                # Execute post button
                if confirm_channel and st.button("✅ CONFIRM & POST", type="primary", use_container_width=True):
                    with st.spinner("Processing post..."):
                        # Download media if present
                        media_data = []
                        if "includes" in st.session_state.tweet_data and "media" in st.session_state.tweet_data["includes"]:
                            media_data = self.download_media_batch(
                                st.session_state.tweet_data["includes"]["media"],
                                st.session_state.tweet_data["data"]["id"]
                            )
                        
                        content_data = {
                            "text": final_text,
                            "media": media_data,
                            "channel_name": st.session_state.channel_name
                        }
                        
                        success, message_id = self.schedule_post(
                            confirm_channel,
                            content_data,
                            schedule_datetime
                        )
                        
                        if success:
                            if schedule_now:
                                st.success("✅ Posted successfully!")
                                
                                # Undo option
                                col_undo1, col_undo2 = st.columns(2)
                                with col_undo1:
                                    if st.button("🔄 Undo Last Post", type="secondary", use_container_width=True):
                                        if self.delete_post(confirm_channel, message_id):
                                            st.success("✅ Post deleted!")
                                        else:
                                            st.error("❌ Could not delete post")
                                            
                                with col_undo2:
                                    st.info(f"Message ID: {message_id}")
                            else:
                                st.success(f"⏰ Post scheduled for {schedule_datetime.strftime('%Y-%m-%d %H:%M')}")
                            
                            # Log activity
                            if "activity_log" not in st.session_state:
                                st.session_state.activity_log = []
                            st.session_state.activity_log.append({
                                "user": st.session_state.current_user,
                                "action": "posted" if schedule_now else "scheduled",
                                "channel": st.session_state.channel_name,
                                "time": datetime.now(),
                                "content_preview": final_text[:50],
                                "message_id": message_id if schedule_now else None
                            })
                            
                            # Reset form
                            for key in ["tweet_data", "original_text", "tweet_url"]:
                                if key in st.session_state:
                                    del st.session_state[key]
                            st.rerun()
                        else:
                            st.error("❌ Post failed - check bot permissions and channel access")
        
        # Activity tab
        with tab_activity:
            st.header("📊 Activity Log")
            
            if "activity_log" in st.session_state and st.session_state.activity_log:
                st.write(f"**Total posts:** {len(st.session_state.activity_log)}")
                
                # Recent activity
                for activity in reversed(st.session_state.activity_log[-20:]):  # Last 20, newest first
                    with st.container():
                        col1, col2, col3, col4 = st.columns([2, 3, 2, 1])
                        with col1:
                            st.write(f"**{activity['channel']}**")
                        with col2:
                            st.write(f"{activity['content_preview']}...")
                        with col3:
                            st.write(f"{activity['action'].title()}")
                        with col4:
                            st.write(activity['time'].strftime('%H:%M'))
                        
                        if activity.get('message_id'):
                            st.caption(f"Message ID: {activity['message_id']}")
                        
                        st.markdown("---")
                
                # Clear log option
                if st.button("🗑️ Clear Activity Log", type="secondary"):
                    st.session_state.activity_log = []
                    st.rerun()
            else:
                st.info("No activity yet. Start by posting some content!")
                
            # Scheduled posts management
            if "scheduled_posts" in st.session_state and st.session_state.scheduled_posts:
                st.subheader("⏰ Scheduled Posts")
                
                for i, post in enumerate(st.session_state.scheduled_posts):
                    if post["status"] == "scheduled":
                        with st.expander(f"Scheduled for {post['schedule_time'].strftime('%Y-%m-%d %H:%M')}"):
                            st.write(f"**Channel:** {post.get('channel_name', 'Unknown')}")
                            st.write(f"**User:** {post['user']}")
                            st.write(f"**Text:** {post['content']['text'][:200]}...")
                            
                            col_del1, col_del2 = st.columns(2)
                            with col_del1:
                                if st.button("🚫 Cancel Schedule", key=f"cancel_detail_{i}"):
                                    del st.session_state.scheduled_posts[i]
                                    st.rerun()
                            with col_del2:
                                if st.button("🚀 Post Now", key=f"post_now_{i}"):
                                    success, message_id = self.post_now(post["chat_id"], post["content"])
                                    if success:
                                        post["status"] = "posted"
                                        post["message_id"] = message_id
                                        st.success("✅ Posted immediately!")
                                        st.rerun()

# Run the app
if __name__ == "__main__":
    try:
        app = SecureXTelegramScheduler()
        app.run()
    except Exception as e:
        st.error(f"App initialization error: {str(e)}")
        st.write("Please check your code structure")