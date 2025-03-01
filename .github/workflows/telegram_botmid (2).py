import logging
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters
from stripe_checkermid import StripeChecker
import json

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# Define a few command handlers
def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Hi! Send me your card details in the format: cc|month|year|cvv')

def check_card(update: Update, context: CallbackContext) -> None:
    card_details = update.message.text.split('|')
    if len(card_details) != 4:
        update.message.reply_text('Invalid card details format. Please use the format: cc|month|year|cvv')
        return

    cc, month, year, cvv = card_details
    checker = StripeChecker()
    result = checker.process_card(cc, month, year, cvv)
    
    # Create a more user-friendly response
    masked_cc = f"**** **** **** {cc[-4:]}" if len(cc) >= 4 else "Card"
    response_message = f"\ud83d\udcb3 {masked_cc}\n\n"
    
    if result['success']:
        response_message += "\u2705 CARD APPROVED\n"
        response_message += f"Message: {result['message']}\n\n"
        
        # Get response data
        response_data = result.get('response', {})
        
        # Add JSON-like formatted response
        response_message += "```\n"
        response_message += "{\n"
        response_message += f'    "success": {result["success"]},\n'
        response_message += f'    "message": "{result["message"]}",\n'
        response_message += '    "response": {\n'
        
        if isinstance(response_data, dict):
            for key, value in response_data.items():
                if isinstance(value, str):
                    response_message += f'        "{key}": "{value}",\n'
                else:
                    response_message += f'        "{key}": {value},\n'
        
        # Remove trailing comma
        if response_message.endswith(',\n'):
            response_message = response_message[:-2] + '\n'
            
        response_message += '    }\n'
        response_message += "}\n```"
        
    else:
        response_message += "\u274c CARD DECLINED\n\n"
        
        # Get detailed reason 
        reason = result.get('reason', '')
        if 'insufficient_funds' in reason.lower():
            response_message += "\u2022 Status: Card is valid but has insufficient balance\n\n"
        
        # Add JSON-like formatted response
        response_message += "```\n"
        response_message += "{\n"
        response_message += f'    "success": {result["success"]},\n'
        response_message += f'    "message": "{result["message"]}",\n'
        response_message += '    "response": {\n'
        
        response_data = result.get('response', {})
        if isinstance(response_data, dict):
            for key, value in response_data.items():
                if isinstance(value, str):
                    response_message += f'        "{key}": "{value}",\n'
                else:
                    response_message += f'        "{key}": {value},\n'
        
        # Remove trailing comma
        if response_message.endswith(',\n'):
            response_message = response_message[:-2] + '\n'
            
        response_message += '    }\n'
        response_message += "}\n```"
    
    update.message.reply_text(response_message)

def main() -> None:
    # Replace 'YOUR_TOKEN' with your bot's API token
    updater = Updater('7920694566:AAHCFNcUxXpTOJkqU6wi9vuULNC5fDxMoBI')

    dispatcher = updater.dispatcher

    # on different commands - answer in Telegram
    dispatcher.add_handler(CommandHandler("start", start))

    # on noncommand i.e message - check card
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, check_card))

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT, SIGTERM or SIGABRT
    updater.idle()

if __name__ == '__main__':
    main()