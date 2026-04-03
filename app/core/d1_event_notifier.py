"""
Destiny 1 Event Notifications System
Gestisce notifiche push per eventi pubblici imminenti
"""
import json
import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from pathlib import Path

from app.core.d1_events import D1EventManager

logger = logging.getLogger(__name__)

class D1EventNotifier:
    """Gestisce notifiche push per eventi D1"""
    
    def __init__(self, telegram_adapter, storage_path: str = None):
        self.telegram = telegram_adapter
        self.event_manager = D1EventManager()
        
        # File per memorizzare iscrizioni utente
        if storage_path is None:
            storage_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data")
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.subscriptions_file = self.storage_path / "d1_event_subscriptions.json"
        self.notified_events_file = self.storage_path / "d1_notified_events.json"
        
        # Cache in memoria
        self.subscriptions: Dict[int, Dict] = {}  # chat_id -> {planets: [], last_notified: {}
        self.notified_events: Dict[str, datetime] = {}  # event_key -> timestamp
        
        # Carica dati esistenti
        self._load_data()
        
        # Task dello scheduler
        self._scheduler_task = None
        self._running = False
    
    def _load_data(self):
        """Carica iscrizioni e notifiche precedenti"""
        try:
            if self.subscriptions_file.exists():
                with open(self.subscriptions_file, 'r') as f:
                    data = json.load(f)
                    # Converte le chiavi stringa in int (chat_id)
                    self.subscriptions = {int(k): v for k, v in data.items()}
                logger.info(f"[D1 Notifier] Caricate {len(self.subscriptions)} iscrizioni")
            
            if self.notified_events_file.exists():
                with open(self.notified_events_file, 'r') as f:
                    data = json.load(f)
                    self.notified_events = {k: datetime.fromisoformat(v) for k, v in data.items()}
                logger.info(f"[D1 Notifier] Caricate {len(self.notified_events)} notifiche precedenti")
        except Exception as e:
            logger.error(f"[D1 Notifier] Errore caricamento dati: {e}")
    
    def _save_data(self):
        """Salva iscrizioni e notifiche"""
        try:
            with open(self.subscriptions_file, 'w') as f:
                json.dump(self.subscriptions, f, indent=2)
            
            with open(self.notified_events_file, 'w') as f:
                # Converte datetime in stringa ISO
                data = {k: v.isoformat() for k, v in self.notified_events.items()}
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"[D1 Notifier] Errore salvataggio dati: {e}")
    
    def subscribe(self, chat_id: int, planets: List[str] = None, notify_before_minutes: int = 5) -> bool:
        """Iscrivi un utente alle notifiche eventi"""
        try:
            self.subscriptions[chat_id] = {
                "planets": planets or [],  # Vuoto = tutti i pianeti
                "notify_before_minutes": notify_before_minutes,
                "subscribed_at": datetime.utcnow().isoformat(),
                "active": True
            }
            self._save_data()
            logger.info(f"[D1 Notifier] Chat {chat_id} iscritta alle notifiche")
            return True
        except Exception as e:
            logger.error(f"[D1 Notifier] Errore iscrizione: {e}")
            return False
    
    def unsubscribe(self, chat_id: int) -> bool:
        """Disiscrivi un utente"""
        try:
            if chat_id in self.subscriptions:
                del self.subscriptions[chat_id]
                self._save_data()
                logger.info(f"[D1 Notifier] Chat {chat_id} disiscritta")
                return True
            return False
        except Exception as e:
            logger.error(f"[D1 Notifier] Errore disiscrizione: {e}")
            return False
    
    def get_subscription(self, chat_id: int) -> Optional[Dict]:
        """Ottiene lo stato iscrizione di un utente"""
        return self.subscriptions.get(chat_id)
    
    def is_subscribed(self, chat_id: int) -> bool:
        """Verifica se un utente è iscritto"""
        return chat_id in self.subscriptions and self.subscriptions[chat_id].get("active", True)
    
    def _generate_event_key(self, event: Dict) -> str:
        """Genera una chiave unica per un evento"""
        return f"{event['planet']}_{event['location']}_{event['type']}_{event['predicted_time'].isoformat()}"
    
    def _should_notify(self, event: Dict, notify_before_minutes: int) -> bool:
        """Determina se bisogna notificare un evento"""
        time_until = event["time_until"]
        total_seconds = time_until.total_seconds()
        
        # Notifica solo se l'evento è tra notify_before_minutes e notify_before_minutes-1 minuti
        # Es: se notify_before_minutes=5, notifica quando mancano 5-4 minuti
        notify_window_start = notify_before_minutes * 60
        notify_window_end = (notify_before_minutes - 1) * 60
        
        if not (notify_window_end < total_seconds <= notify_window_start):
            return False
        
        # Verifica se già notificato
        event_key = self._generate_event_key(event)
        if event_key in self.notified_events:
            last_notified = self.notified_events[event_key]
            # Non notificare di nuovo se è passato meno di 1 ora
            if datetime.utcnow() - last_notified < timedelta(hours=1):
                return False
        
        return True
    
    async def _send_notification(self, chat_id: int, event: Dict):
        """Invia notifica a un utente con nuovo formato"""
        try:
            time_str = self.event_manager.format_time_until(event["time_until"], show_seconds=True)
            
            # Status indicator basato sul tempo
            seconds_until = event["time_until"].total_seconds()
            if seconds_until < 300:  # < 5 min
                status = "🟡 Imminent"
            elif seconds_until < 600:  # < 10 min
                status = "🟠 Soon"
            else:
                status = "🟢 Upcoming"
            
            # Difficulty
            difficulty = event.get("difficulty", "Medium")
            
            # Emoji per tipo evento
            event_emoji = "🛡️" if "Warsat" in event["type"] else "🤖" if "Walker" in event["type"] else "⚡"
            
            # Format messaggio con nuovo stile
            message = (
                f"🔔 <b>EVENTO IMMINENTE!</b>\n\n"
                f"{status} {event_emoji} <b>{event['type']}</b>\n"
                f"📍 {event['planet']} - {event['location']}\n"
                f"⏱️ <code>{time_str}</code> | 💪 {difficulty}\n"
                f"🎁 {event.get('rewards', 'Materiali')}\n"
            )
            
            if event.get("heroic_possible"):
                message += f"⭐ Heroic mode disponibile!\n"
            
            message += f"\n<i>Usa /d1_events per vedere tutti gli eventi</i>"
            
            await self.telegram.send_message(chat_id, message)
            
            # Marca come notificato
            event_key = self._generate_event_key(event)
            self.notified_events[event_key] = datetime.utcnow()
            self._save_data()
            
            logger.info(f"[D1 Notifier] Notifica inviata a {chat_id} per {event['type']} @ {event['location']}")
            
        except Exception as e:
            logger.error(f"[D1 Notifier] Errore invio notifica a {chat_id}: {e}")
    
    async def check_and_notify(self):
        """Controlla eventi imminenti e invia notifiche"""
        try:
            if not self.subscriptions:
                return
            
            # Ottieni eventi urgenti
            urgent_events = self.event_manager.get_urgent_events()
            
            if not urgent_events:
                return
            
            logger.info(f"[D1 Notifier] {len(urgent_events)} eventi urgenti trovati")
            
            for chat_id, subscription in self.subscriptions.items():
                if not subscription.get("active", True):
                    continue
                
                notify_before = subscription.get("notify_before_minutes", 5)
                subscribed_planets = subscription.get("planets", [])
                
                for event in urgent_events:
                    # Filtra per pianeta se specificato
                    if subscribed_planets and event["planet"] not in subscribed_planets:
                        continue
                    
                    # Verifica se notificare
                    if self._should_notify(event, notify_before):
                        await self._send_notification(chat_id, event)
                        # Piccola pausa per evitare rate limit
                        await asyncio.sleep(0.5)
                        
        except Exception as e:
            logger.error(f"[D1 Notifier] Errore check_and_notify: {e}")
    
    async def start_scheduler(self, check_interval_seconds: int = 60):
        """Avvia lo scheduler in background"""
        if self._running:
            logger.warning("[D1 Notifier] Scheduler già in esecuzione")
            return
        
        self._running = True
        logger.info(f"[D1 Notifier] Scheduler avviato (check ogni {check_interval_seconds}s)")
        
        while self._running:
            try:
                await self.check_and_notify()
                await asyncio.sleep(check_interval_seconds)
            except Exception as e:
                logger.error(f"[D1 Notifier] Errore scheduler: {e}")
                await asyncio.sleep(check_interval_seconds)
    
    def stop_scheduler(self):
        """Ferma lo scheduler"""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
        logger.info("[D1 Notifier] Scheduler fermato")
    
    def get_stats(self) -> Dict:
        """Statistiche del notificatore"""
        return {
            "total_subscriptions": len(self.subscriptions),
            "total_notified_events": len(self.notified_events),
            "scheduler_running": self._running,
            "active_subscribers": sum(1 for s in self.subscriptions.values() if s.get("active", True))
        }


# Singleton instance (verà inizializzato dall'orchestrator)
d1_event_notifier: Optional[D1EventNotifier] = None

def init_notifier(telegram_adapter):
    """Inizializza il notificatore globale"""
    global d1_event_notifier
    if d1_event_notifier is None:
        d1_event_notifier = D1EventNotifier(telegram_adapter)
    return d1_event_notifier
