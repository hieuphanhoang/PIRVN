import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from phase6_agents.agent import Agent
from phase6_agents.deals import Opportunity
from shared.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from shared.currency import format_vnd


class MessagingAgent(Agent):
    name = "Messaging Agent"
    color = Agent.WHITE

    def __init__(self):
        self.log("Messaging Agent is initializing")
        self.bot_token = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        if not self.bot_token or not self.chat_id:
            self.log("WARNING: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set in .env")
        self.log("Messaging Agent is ready")

    def push(self, text: str):
        if not self.bot_token or not self.chat_id:
            self.log(f"[DRY RUN] Would send: {text[:100]}...")
            return
        self.log("Messaging Agent is sending Telegram notification")
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            requests.post(url, json={
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            }, timeout=10)
        except Exception as e:
            self.log(f"Telegram send failed: {e}")

    def alert(self, opportunity: Opportunity):
        text = (
            f"🔥 <b>Deal Alert!</b>\n\n"
            f"💰 Gia ban: {format_vnd(opportunity.deal.price)}\n"
            f"📊 Gia uoc tinh: {format_vnd(opportunity.estimate)}\n"
            f"✅ Giam: {format_vnd(opportunity.discount)}\n\n"
            f"{opportunity.deal.product_description[:200]}\n\n"
            f"🔗 {opportunity.deal.url}"
        )
        self.push(text)
        self.log("Messaging Agent has completed")

    def alert_daily_summary(self, opportunities: list):
        if not opportunities:
            return
        lines = [f"📋 <b>PIRVN Daily Deals — {len(opportunities)} san pham hoi</b>\n"]
        for i, opp in enumerate(opportunities, 1):
            lines.append(
                f"\n<b>{i}. {opp.deal.product_description[:100]}</b>\n"
                f"   💰 Gia ban: {format_vnd(opp.deal.price)}\n"
                f"   📊 Uoc tinh: {format_vnd(opp.estimate)}\n"
                f"   ✅ Giam: {format_vnd(opp.discount)}\n"
                f"   🔗 {opp.deal.url}"
            )
        text = "\n".join(lines)
        if len(text) > 4000:
            text = text[:3950] + "\n\n... (truncated)"
        self.push(text)
        self.log(f"Messaging Agent sent daily summary with {len(opportunities)} deals")

    def craft_message(self, description: str, deal_price: float, estimated_value: float) -> str:
        from litellm import completion
        user_prompt = (
            "Summarize this deal in 2-3 exciting sentences for a Vietnamese push notification.\n"
            f"Product: {description}\n"
            f"Deal price: {deal_price:,.0f} VND\n"
            f"Estimated value: {estimated_value:,.0f} VND\n\n"
            "Respond only with the notification text in Vietnamese."
        )
        response = completion(
            model=f"ollama/{os.getenv('OLLAMA_MODEL', 'qwen3:4b')}",
            messages=[{"role": "user", "content": user_prompt}],
            api_base=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        )
        return response.choices[0].message.content

    def notify(self, description: str, deal_price: float, estimated_value: float, url: str):
        self.log("Messaging Agent is crafting a message")
        text = self.craft_message(description, deal_price, estimated_value)
        self.push(text[:300] + f"\n\n🔗 {url}")
        self.log("Messaging Agent has completed")
