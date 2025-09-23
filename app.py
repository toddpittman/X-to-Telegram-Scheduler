# app.py
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

# Dark theme for mobile optimization
st.markdown("""
<style>
    [data-testid="stAppViewContainer"] {
        background-color: #0e1117;
        color: #fafafa;
    }
    .stTextInput > div > div > input {
        background-color: #1f2937;
        color: #fafafa;
    }
    .stTextArea > div > div > textarea {
        background-color: #1f2937;
        color: #fafafa;
    }
    .stButton>button {
        width: 100%;
        margin: 5px 0;
    }
    @media (max-width: 640px) {
        .stApp {
            padding: 10px;
        }
        .stTextArea {
            height: 120px !important;
        }
    }
</style>
""", unsafe_allow_html=True)

class SecureXTelegramScheduler:
    def __init__(self):
        self.config = self.get_config()
        self.check_team_access()
        
    def get_config(self):
        """Load secure config from environment"""
        try:
            return {
                "X_BEARER_TOKEN": os.getenv("X_BEARER_TOKEN", st.secrets.get("X_BEARER_TOKEN")),
                "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN", st.secrets.get("TELEGRAM_BOT_TOKEN")),
                "APP_PASSWORD": os.getenv("APP_PASSWORD", st.secrets.get("APP_PASSWORD")),
                "TEAM_PASSWORDS": json.loads(os.getenv("TEAM_PASSWORDS", st.secrets.get("TEAM_PASSWORDS", "{}")))
            }
        except Exception as e:
            st.error(f"Config error: {e}")
            st.stop()
    
    def check_team_access(self):
        """Team authentication system"""
        if "user_authenticated" not in st.session_state:
            st.session_state.user_authenticated = False
            st.session_state.current_user = None
        
        if not st.session_state.user_authenticated:
            st.title("🔐 Team Access Required")
            st.markdown("**Enterprise Content Scheduler**")
            
            username = st.text_input("Team Member:", placeholder="john_doe")
            password = st.text_input("Password:", type="password")
            
            if st.button("🔑 Login", type="primary", use_container_width=True):
                if username in self.config["TEAM_PASSWORDS"] and \
                   password == self.config["TEAM_PASSWORDS"][username]:
                    st.session_state.user_authenticated = True
                    st.session_state.current_user = username
                    st.session_state.app_password = True
                    st.success(f"Welcome back, {username.title()}!")
                    st.rerun()
                else:
                    st.error("❌ Invalid credentials")
            
            # Main app password check
            if not st.session_state.app_password:
                app_pass = st.text_input("App Admin Password:", type="password", key="admin_pass")
                if st.button("Setup App", key="setup", type="primary", use_container_width=True):
                    if app_pass == self.config["APP_PASSWORD"]:
                        st.session_state.app_password = True
                        st.rerun()
                    else:
                        st.error("❌ Admin password incorrect")
            
            st.stop()
        
        # Logout option
        if st.sidebar.button("🚪 Logout", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    
    def extract_tweet_id(self, url):
        """Extract tweet ID - handles all URL formats"""
        clean_url = re.sub(r'\?.*$', '', url)
        match = re.search(r'/status/(\d+)', clean_url)
        return match.group(1) if match else None
    
    def fetch_tweet(self, tweet_id):
        """Fetch tweet with full expansions"""
        headers = {"Authorization": f"Bearer {self.config['X_BEARER_TOKEN']}"}
        params = {
            "expansions": "attachments.media_keys,author_id",
            "tweet.fields": "attachments,author_id,text,created_at",
            "media.fields": "type,url,variants",
            "user.fields": "name,username"
        }
        
        try:
            response = requests.get(
                f"https://api.twitter.com/2/tweets/{tweet_id}",
                headers=headers,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            return data if "data" in data else None
        except Exception as e:
            st.error(f"X API Error: {e}")
            return None
    
    def download_media_batch(self, media_list, tweet_id):
        """Download multiple media with size limits"""
        downloaded = []
        total_size = 0
        
        for i, media in enumerate(media_list[:10]):  # Telegram limit
            try:
                if media["type"] == "photo":
                    response = requests.get(media["url"], timeout=30)
                    response.raise_for_status()
                    
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
                    temp_file.write(response.content)
                    temp_file.close()
                    
                    if os.path.getsize(temp_file.name) > 10 * 1024 * 1024:
                        os.unlink(temp_file.name)
                        continue
                    
                    downloaded.append({
                        "type": "photo",
                        "file": temp_file.name,
                        "media_key": media["media_key"]
                    })
                    total_size += os.path.getsize(temp_file.name)
                    
                elif media["type"] == "video":
                    variants = [v for v in media.get("variants", []) if v.get("bitrate")]
                    if variants:
                        for variant in sorted(variants, key=lambda x: x.get("bitrate", 0), reverse=True):
                            try:
                                response = requests.get(variant["url"], stream=True, timeout=30)
                                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
                                
                                for chunk in response.iter_content(8192):
                                    if len(chunk) == 0:
                                        break
                                    temp_file.write(chunk)
                                    if temp_file.tell() > 50 * 1024 * 1024:
                                        break
                                
                                temp_file.close()
                                
                                if os.path.getsize(temp_file.name) <= 50 * 1024 * 1024:
                                    downloaded.append({
                                        "type": "video",
                                        "file": temp_file.name,
                                        "media_key": media["media_key"]
                                    })
                                    total_size += os.path.getsize(temp_file.name)
                                    break
                                else:
                                    os.unlink(temp_file.name)
                                    
                            except:
                                if os.path.exists(temp_file.name):
                                    os.unlink(temp_file.name)
                                continue
                                
            except Exception as e:
                st.warning(f"Media {i+1} download failed: {e}")
                continue
        
        st.info(f"✅ Downloaded {len(downloaded)} items ({total_size/1024/1024:.1f}MB)")
        return downloaded
    
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
            return True
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
        """Post media album"""
        url = f"https://api.telegram.org/bot{self.config['TELEGRAM_BOT_TOKEN']}/sendMediaGroup"
        
        media_group = []
        for i, media in enumerate(media_list):
            with open(media["file"], "rb") as file:
                item = {
                    "type": media["type"],
                    "media": file,
                    "caption": text if i == 0 else ""
                }
                media_group.append(item)
        
        try:
            files = {"media": (None, json.dumps(media_group))}
            data = {"chat_id": chat_id}
            
            response = requests.post(url, files=files, data=data, timeout=120)
            response.raise_for_status()
            
            result = response.json()
            if result.get("ok"):
                self.cleanup_media(media_list)
                return True, result["result"][0]["message_id"]
            return False, None
        except Exception as e:
            st.error(f"Post failed: {e}")
            self.cleanup_media(media_list)
            return False, None
    
    def post_text(self, chat_id, text):
        """Post text only (up to 4,096 chars)"""
        url = f"https://api.telegram.org/bot{self.config['TELEGRAM_BOT_TOKEN']}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": text[:4096],  # Telegram Premium limit
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        
        try:
            response = requests.post(url, data=data, timeout=30)
            response.raise_for_status()
            result = response.json()
            return result.get("ok"), result["result"]["message_id"] if result.get("ok") else None
        except Exception as e:
            st.error(f"Text post failed: {e}")
            return False, None
    
    def delete_post(self, chat_id, message_id):
        """Delete post for undo functionality"""
        url = f"https://api.telegram.org/bot{self.config['TELEGRAM_BOT_TOKEN']}/deleteMessage"
        data = {"chat_id": chat_id, "message_id": message_id}
        
        try:
            response = requests.post(url, data=data, timeout=10)
            return response.json().get("ok", False)
        except:
            return False
    
    def cleanup_media(self, media_list):
        """Clean up temp files"""
        for media in media_list:
            if os.path.exists(media["file"]):
                os.unlink(media["file"])
    
    def format_channel_id(self, channel_input):
        """Smart channel ID formatting"""
        channel_input = channel_input.strip()
        if channel_input.isdigit():
            return f"-100{channel_input}"
        elif channel_input.startswith("@"):
            return channel_input
        elif channel_input.startswith("-"):
            return channel_input if channel_input.startswith("-100") else f"-100{channel_input}"
        else:
            return f"@{channel_input}"
    
    def run(self):
        """Main app interface"""
        st.title("⏰ X → Telegram Enterprise Scheduler")
        st.markdown(f"**Logged in as:** {st.session_state.current_user.title()}")
        st.markdown("---")
        
        # Channel Manager
        with st.sidebar:
            st.header("📱 Channel Manager")
            
            if "channels" not in st.session_state:
                st.session_state.channels = {}
                # Preload with 25 placeholders (update with real names/IDs)
                for i in range(1, 26):
                    st.session_state.channels[f"Channel {i}"] = f"-100123456789{i}"
            
            # Add/Edit channel
            st.subheader("Add/Edit Channel")
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Name", key="new_channel_name")
            with col2:
                cid = st.text_input("ID/@handle", key="new_channel_id")
            
            if st.button("➕ Save Channel", use_container_width=True) and name and cid:
                st.session_state.channels[name] = self.format_channel_id(cid)
                st.success(f"Added {name}")
                st.rerun()
            
            # Channel list with links
            st.subheader("Your Channels")
            if st.session_state.channels:
                for name, cid in st.session_state.channels.items():
                    col_a, col_b = st.columns([3, 1])
                    with col_a:
                        st.write(f"📢 {name} ({cid[:20]}...)")
                    with col_b:
                        if st.button("Select", key=f"ch_{name}"):
                            st.session_state.selected_channel = cid
                            st.session_state.channel_name = name
                            st.rerun()
            
            # Scheduled posts overview
            if "scheduled_posts" in st.session_state and st.session_state.scheduled_posts:
                st.subheader("⏰ Scheduled")
                for i, post in enumerate(st.session_state.scheduled_posts):
                    if post["status"] == "scheduled":
                        st.write(f"**{post.get('channel_name', 'Unknown')}** - {post['schedule_time'].strftime('%H:%M %d/%m')}")
                        if st.button("🚫 Cancel", key=f"cancel_{i}"):
                            del st.session_state.scheduled_posts[i]
                            st.rerun()
        
        # Main workflow
        tab1, tab2 = st.tabs(["📝 New Post", "📊 Activity"])
        
        with tab1:
            col1, col2 = st.columns([1, 3])
            
            with col1:
                st.subheader("Step 1: Analyze X Post")
                x_url = st.text_input("Paste X URL", placeholder="https://x.com/user/status/123...")
                
                if st.button("🔍 Analyze", type="primary", use_container_width=True):
                    tweet_id = self.extract_tweet_id(x_url)
                    if tweet_id:
                        with st.spinner("Fetching..."):
                            tweet_data = self.fetch_tweet(tweet_id)
                            if tweet_data:
                                st.session_state.tweet_data = tweet_data
                                st.session_state.original_text = tweet_data["data"].get("text", "")
                                st.session_state.tweet_url = x_url
                                st.rerun()
                            else:
                                st.error("Failed to fetch tweet")
                    else:
                        st.error("Invalid URL")
            
            with col2:
                if "tweet_data" in st.session_state:
                    st.subheader("Preview")
                    tweet = st.session_state.tweet_data["data"]
                    
                    # Author
                    if "includes" in st.session_state.tweet_data and "users" in st.session_state.tweet_data["includes"]:
                        user = next((u for u in st.session_state.tweet_data["includes"]["users"] 
                                   if u["id"] == tweet["author_id"]), None)
                        if user:
                            st.markdown(f"**{user['name']}** (@{user['username']})")
                    
                    # Text preview
                    st.text_area("Original:", st.session_state.original_text, height=100, disabled=True)
                    
                    # Media preview
                    if "includes" in st.session_state.tweet_data and "media" in st.session_state.tweet_data["includes"]:
                        media_list = st.session_state.tweet_data["includes"]["media"]
                        cols = st.columns(min(3, len(media_list)))
                        for i, media in enumerate(media_list[:3]):
                            with cols[i]:
                                if media["type"] == "photo":
                                    st.image(media["url"], use_column_width=True)
                                elif media["type"] == "video":
                                    st.write(f"🎥 Video {i+1}")
        
        # Post editor
        if "tweet_data" in st.session_state:
            st.subheader("Step 2: Customize")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # Channel selection
                st.markdown("**Channel:**")
                if "selected_channel" in st.session_state:
                    st.info(f"{st.session_state.channel_name}: {st.session_state.selected_channel}")
                
                # Channel-specific link
                if "selected_channel" in st.session_state:
                    link_key = f"link_{st.session_state.channel_name.replace(' ', '_')}"
                    default_link = st.session_state.get(link_key, "")
                    channel_link = st.text_input("Channel Link", value=default_link, key=link_key)
                    if channel_link:
                        st.session_state[link_key] = channel_link
            
            with col2:
                # Text editing
                edited_text = st.text_area(
                    "Edit text (4,096 chars max):",
                    value=st.session_state.original_text,
                    height=150,
                    key="edit_text"
                )
            
            with col3:
                # Scheduling
                st.markdown("**Schedule:**")
                schedule_now = st.checkbox("Post Now", value=True)
                
                if not schedule_now:
                    schedule_date = st.date_input("Date", min_value=datetime.now().date())
                    schedule_time = st.time_input("Time", value=datetime.now().time())
                    schedule_datetime = datetime.combine(schedule_date, schedule_time)
                else:
                    schedule_datetime = None
            
            # Channel links management
            with st.expander("🔗 Manage Channel Links"):
                st.markdown("Set default links for each channel:")
                for name in st.session_state.channels.keys():
                    link_key = f"link_{name.replace(' ', '_')}"
                    default_link = st.session_state.get(link_key, "")
                    new_link = st.text_input(f"{name}:", value=default_link, key=f"manage_{name}")
                    if new_link != default_link:
                        st.session_state[link_key] = new_link
            
            # Final preview & safety checks
            st.subheader("Step 3: Review & Confirm")
            
            final_text = edited_text[:4096]  # Telegram Premium limit
            if "selected_channel" in st.session_state:
                link_key = f"link_{st.session_state.channel_name.replace(' ', '_')}"
                if st.session_state.get(link_key):
                    final_text += f'\n\n🔗 <a href="{st.session_state[link_key]}">Visit Channel</a>'
            
            with st.expander("👁️ Final Preview", expanded=True):
                st.markdown("**Text:**")
                st.markdown(final_text[:1000] + "..." if len(final_text) > 1000 else final_text)
                
                if "includes" in st.session_state.tweet_data and "media" in st.session_state.tweet_data["includes"]:
                    st.markdown("**Media:** Album of photos/videos")
            
            # SAFETY CONFIRMATION
            col_a, col_b = st.columns(2)
            with col_a:
                st.warning("**⚠️ Double-check channel & content**")
                confirm_channel = st.selectbox(
                    "Confirm posting to:",
                    options=[st.session_state.selected_channel] if "selected_channel" in st.session_state else ["None"],
                    key="confirm_channel"
                )
            
            with col_b:
                st.info(f"**Posting as:** {st.session_state.current_user}")
                post_type = "⏰ Scheduled" if not schedule_now else "🚀 Immediate"
                st.info(post_type)
            
            # EXECUTE POST
            if st.button("✅ CONFIRM & POST", type="primary", use_container_width=True) and confirm_channel:
                with st.spinner("Processing..."):
                    # Download media
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
                            st.info(f"Message ID: {message_id}")
                            
                            # Undo option
                            if st.button("🔄 Undo Last Post", type="secondary", use_container_width=True):
                                if self.delete_post(confirm_channel, message_id):
                                    st.success("✅ Post deleted!")
                                else:
                                    st.error("❌ Could not delete post")
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
                            "content_preview": final_text[:50]
                        })
                        
                        # Reset form
                        for key in ["tweet_data", "original_text", "tweet_url"]:
                            if key in st.session_state:
                                del st.session_state[key]
                        st.rerun()
                    else:
                        st.error("❌ Post failed - check bot permissions")
        
        # Activity tab
        with tab2:
            st.subheader("📊 Activity Log")
            if "activity_log" in st.session_state:
                for activity in st.session_state.activity_log[-10:]:  # Last 10
                    with st.container():
                        col1, col2, col3 = st.columns([2, 2, 1])
                        with col1:
                            st.write(f"**{activity['channel']}**")
                        with col2:
                            st.write(activity['content_preview'] + "...")
                        with col3:
                            st.write(activity['time'].strftime('%H:%M %d/%m'))
                        st.markdown("---")

# Run the app
if __name__ == "__main__":
    app = SecureXTelegramScheduler()
    app.run()