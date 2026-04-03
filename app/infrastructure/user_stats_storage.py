"""
Simple JSON-based storage for user stats
"""
import json
import os
from typing import Dict, List, Optional
from datetime import datetime

class UserStatsStorage:
    """Storage for user D1 stats"""
    
    DATA_FILE = "/tmp/d1_user_stats.json"
    
    @staticmethod
    def _load_data() -> Dict:
        """Load user stats from file"""
        if os.path.exists(UserStatsStorage.DATA_FILE):
            try:
                with open(UserStatsStorage.DATA_FILE, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    @staticmethod
    def _save_data(data: Dict):
        """Save user stats to file"""
        with open(UserStatsStorage.DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    
    @staticmethod
    def save_user_stats(
        chat_id: int,
        gamertag: str,
        membership_id: str,
        kills: int,
        deaths: int,
        hours: int,
        raid_completions: int
    ):
        """Save or update user stats"""
        data = UserStatsStorage._load_data()
        
        user_key = str(chat_id)
        
        data[user_key] = {
            "gamertag": gamertag,
            "membership_id": membership_id,
            "kills": kills,
            "deaths": deaths,
            "hours": hours,
            "raid_completions": raid_completions,
            "kd_ratio": round(kills / max(deaths, 1), 2),
            "last_updated": datetime.utcnow().isoformat()
        }
        
        UserStatsStorage._save_data(data)
    
    @staticmethod
    def get_all_users() -> List[Dict]:
        """Get all users with stats"""
        data = UserStatsStorage._load_data()
        return list(data.values())
    
    @staticmethod
    def get_leaderboard(sort_by: str = "raid_completions", limit: int = 10) -> List[Dict]:
        """Get leaderboard sorted by specific stat"""
        users = UserStatsStorage.get_all_users()
        
        # Sort by specified field
        valid_fields = ["kills", "kd_ratio", "hours", "raid_completions"]
        if sort_by not in valid_fields:
            sort_by = "raid_completions"
        
        sorted_users = sorted(users, key=lambda x: x.get(sort_by, 0), reverse=True)
        return sorted_users[:limit]
    
    @staticmethod
    def get_user_count() -> int:
        """Get total number of users with stats"""
        data = UserStatsStorage._load_data()
        return len(data)

# Convenience functions
def save_user_stats(*args, **kwargs):
    return UserStatsStorage.save_user_stats(*args, **kwargs)

def get_leaderboard(*args, **kwargs):
    return UserStatsStorage.get_leaderboard(*args, **kwargs)

def get_all_users():
    return UserStatsStorage.get_all_users()
