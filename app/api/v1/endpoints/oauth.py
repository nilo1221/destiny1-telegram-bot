from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from app.services.orchestrator import ServiceOrchestrator
from app.services.oauth_handler import get_oauth_handler
from app.core.logging import get_logger

logger = get_logger("oauth")
router = APIRouter()

# Export the router
__all__ = ["router"]

@router.get("/auth")
async def get_oauth_url(chat_id: int = None):
    """Generate OAuth authorization URL with automatic callback"""
    try:
        oauth = get_oauth_handler()
        # Include chat_id in state for automatic processing
        state = f"auto_auth_{chat_id}" if chat_id else "manual_auth"
        auth_url = oauth.get_auth_url(state=state)
        
        return {
            "status": "success",
            "auth_url": auth_url,
            "auto_callback": bool(chat_id),
            "message": "Clicca il link per autorizzare. Il codice verrà processato automaticamente!"
        }
    except Exception as e:
        logger.error(f"Error generating OAuth URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auth/page")
async def oauth_page():
    """Redirect to user-friendly OAuth page"""
    return RedirectResponse(url="/static/oauth_callback.html")


@router.get("/callback")
async def oauth_callback_get(code: str = None, state: str = None, error: str = None):
    """OAuth callback endpoint with automatic Telegram notification"""
    if error:
        # Check if it was auto-auth
        if state and state.startswith("auto_auth_"):
            chat_id = state.replace("auto_auth_", "")
            await send_oauth_result_to_telegram(chat_id, False, f"Errore OAuth: {error}")
        return RedirectResponse(url=f"/static/oauth_callback.html?error={error}")
    
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")
    
    # Check if auto-auth mode
    if state and state.startswith("auto_auth_"):
        chat_id = int(state.replace("auto_auth_", ""))
        logger.info(f"Auto-authenticating chat {chat_id}")
        
        # Process OAuth automatically
        try:
            from app.services.orchestrator import ServiceOrchestrator
            orchestrator = ServiceOrchestrator()
            result = await orchestrator.handle_oauth_code(chat_id, code)
            
            if result.get("success"):
                await send_oauth_result_to_telegram(chat_id, True, "✅ Autenticazione completata con successo!")
                return RedirectResponse(url=f"/static/oauth_success.html?chat_id={chat_id}&status=success")
            else:
                await send_oauth_result_to_telegram(chat_id, False, f"❌ Errore: {result.get('error', 'Sconosciuto')}")
                return RedirectResponse(url=f"/static/oauth_callback.html?error={result.get('error', 'Auth failed')}")
        except Exception as e:
            logger.error(f"Auto-auth error: {e}")
            await send_oauth_result_to_telegram(chat_id, False, f"❌ Errore sistema: {str(e)}")
            return RedirectResponse(url=f"/static/oauth_callback.html?error={str(e)}")
    
    # Manual mode - redirect to page with code
    return RedirectResponse(url=f"/static/oauth_callback.html?code={code}")


@router.post("/callback")
async def oauth_callback_post(code: str, state: str = None):
    """OAuth callback endpoint - POST version for API"""
    try:
        oauth = get_oauth_handler()
        token_data = await oauth.exchange_code_for_token(code)
        
        # Store token (in production, use secure storage)
        logger.info(f"OAuth successful for state: {state}")
        
        return {
            "status": "success",
            "message": "Authentication successful",
            "access_token": token_data.get("access_token", "")[:10] + "...",  # Partial for security
            "token_type": token_data.get("token_type"),
            "expires_in": token_data.get("expires_in"),
            "refresh_token": token_data.get("refresh_token", "")[:10] + "..."  # Partial for security
        }
    except Exception as e:
        logger.error(f"OAuth callback failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def oauth_status():
    """Check OAuth system status"""
    return {
        "status": "ready",
        "oauth_configured": bool(get_oauth_handler().get_auth_url()),
        "endpoints": {
            "auth": "/auth",
            "callback": "/callback",
            "page": "/auth/page"
        }
    }


async def send_oauth_result_to_telegram(chat_id: int, success: bool, message: str):
    """Send OAuth result notification to Telegram user automatically"""
    try:
        from app.services.adapters import TelegramAdapter
        telegram = TelegramAdapter()
        
        if success:
            full_message = (
                f"🎉 <b>Autenticazione Automatica Completata!</b>\n\n"
                f"✅ {message}\n\n"
                f"🔐 I tuoi token sono salvati in modo sicuro\n"
                f"🔄 Refresh automatico: ATTIVO\n\n"
                f"Ora puoi usare tutti i comandi!"
            )
        else:
            full_message = (
                f"❌ <b>Autenticazione Fallita</b>\n\n"
                f"{message}\n\n"
                f"💡 Usa /auth per riprovare"
            )
        
        await telegram.send_message(chat_id, full_message)
        logger.info(f"OAuth result sent to chat {chat_id}: {'success' if success else 'failed'}")
    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")
