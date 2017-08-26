import logging
import json

from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters,
                          ConversationHandler, CallbackQueryHandler)
from telegram import ChatAction, ParseMode, InlineKeyboardButton, InlineKeyboardMarkup
from peewee import fn

from word import word_query

from model import User, UserVocabularyMapping, Vocabulary, init as model_init

# set logger
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


class WordBot(object):
    def __init__(self, BOT_TOKEN, COUNT_CHECK=5):
        self.updater = Updater(token=BOT_TOKEN)
        dispatcher = self.updater.dispatcher

        self.COUNT_CHECK = COUNT_CHECK

        start_handler = CommandHandler('start', self.start)
        test_handler = CommandHandler('test', self.test)
        review_handler = CommandHandler('review', self.review)
        query_handler = MessageHandler(Filters.text, self.query)

        dispatcher.add_handler(start_handler)
        dispatcher.add_handler(query_handler)
        dispatcher.add_handler(review_handler)
        dispatcher.add_handler(test_handler)
        dispatcher.add_handler(CallbackQueryHandler(self.reply_button_callback))

    def run(self):
        self.updater.start_polling()
        # self.updater.idle()

    @staticmethod
    def start(bot, update):
        bot.sendChatAction(chat_id=update.message.chat_id, action=ChatAction.TYPING)
        user, new_created = User.get_or_create(tgid=str(update.message.from_user.id))
        if new_created:
            bot.send_message(chat_id=update.message.chat_id, text="Hi!")
        else:
            bot.send_message(chat_id=update.message.chat_id, text="Hi, nice to see you again.")

    @staticmethod
    def query(bot, update):
        bot.sendChatAction(chat_id=update.message.chat_id, action=ChatAction.TYPING)
        vocabulary = word_query(update.message.text)
        if vocabulary is not None:
            response = str(vocabulary)
        else:
            response = ':( 500'
        bot.send_message(chat_id=update.message.chat_id, text=response, parse_mode=ParseMode.HTML)
        if vocabulary and vocabulary.audio:
            bot.send_audio(chat_id=update.message.chat_id, audio=open(vocabulary.audio, 'rb'))

        user, new_created = User.get_or_create(tgid=str(update.message.from_user.id))
        if vocabulary is not None:
            mapping, new_created = UserVocabularyMapping.get_or_create(user=user, vocabulary=vocabulary)
            if (not new_created) and mapping.check_times > 0:
                mapping.update(check_times=0).execute()

    @staticmethod
    def review(bot, update):
        bot.sendChatAction(chat_id=update.message.chat_id, action=ChatAction.TYPING)
        user, new_created = User.get_or_create(tgid=str(update.message.from_user.id))
        if new_created or user.uservocabularymapping_set.count() == 0:
            bot.send_message(chat_id=update.message.chat_id, text="you don't have any vocabulary yet!")
            return None
        keyboard = [[InlineKeyboardButton('🔁',
                                          callback_data='{"command": "review", "type": "order", "arg": 0, "check": 0}'),
                     InlineKeyboardButton('🔀',
                                          callback_data='{"command": "review", "type": "shuffle", "arg": 0, "check": 0}')]]
        reply_markup = InlineKeyboardMarkup(keyboard, one_time_keyboard=True)
        bot.send_message(chat_id=update.message.chat_id,
                         text="🐰 OK! Let's start to review.\nPlease select the play mode.",
                         reply_markup=reply_markup)

    @staticmethod
    def test(bot, update):
        bot.sendChatAction(chat_id=update.message.chat_id, action=ChatAction.TYPING)
        word = Vocabulary.select(Vocabulary.id, Vocabulary.word).order_by(fn.Random()).limit(1).first()
        reply = "Test:\n\t%s" % word.word
        keyboard = [[InlineKeyboardButton("❓",
                                          callback_data='{"command": "test", "type": "ask", "arg": %d}' % word.id),
                     InlineKeyboardButton("⏭",
                                          callback_data='{"command": "test", "type": "next"}')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        bot.send_message(chat_id=update.message.chat_id, text=reply, reply_markup=reply_markup)

    def reply_button_callback(self, bot, update):
        query = update.callback_query
        chat_id = query.message.chat_id

        bot.sendChatAction(chat_id=chat_id, action=ChatAction.TYPING)

        try:
            data = json.loads(query.data)
        except:
            data = None

        if not (data and type(data) == dict and 'command' in data):
            bot.edit_message_text(text="unknown command🕴",
                                  chat_id=chat_id,
                                  message_id=query.message.message_id)
            logger.warning(query)
            return

        if data['command'] == 'review':
            _id = data['arg']

            # clear the previous reply button
            bot.edit_message_reply_markup(chat_id=chat_id, message_id=query.message.message_id)

            if data['check'] == 1:
                UserVocabularyMapping.update(check_times=UserVocabularyMapping.check_times + 1) \
                    .where(UserVocabularyMapping.id == _id).execute()
                # bot.edit_message_text(text='🎉', chat_id=chat_id, message_id=query.message.message_id)
                mapping = UserVocabularyMapping.get(id=_id)
                if mapping.check_times >= self.COUNT_CHECK:
                    reply_text = '🎉' * self.COUNT_CHECK
                else:
                    reply_text = '⭐️' * mapping.check_times
                bot.send_message(chat_id=chat_id, text=reply_text)

            if data['type'] == 'order':
                mapping_query = UserVocabularyMapping.select().join(User) \
                    .where((UserVocabularyMapping.id > _id) & (User.tgid == str(chat_id)) \
                           & (UserVocabularyMapping.check_times < self.COUNT_CHECK)) \
                    .order_by(UserVocabularyMapping.id).limit(1)

                # repeat
                if _id > 0 and mapping_query.count() == 0:
                    mapping_query = UserVocabularyMapping.select().join(User) \
                        .where((User.tgid == str(chat_id)) \
                               & (UserVocabularyMapping.check_times < self.COUNT_CHECK)) \
                        .order_by(UserVocabularyMapping.id).limit(1)

                if mapping_query.count() > 0:
                    mapping = mapping_query[0]
                    reply = str(mapping.vocabulary)
                    keyboard = [[InlineKeyboardButton("✅",
                                                      callback_data='{"command": "review", "type": "order", "arg": %d, "check": 1}' % mapping.id),
                                 InlineKeyboardButton("⏭",
                                                      callback_data='{"command": "review", "type": "order", "arg": %d, "check": 0}' % mapping.id), ]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    bot.send_message(chat_id=chat_id, text=reply, reply_markup=reply_markup)
                else:
                    bot.send_message(chat_id=chat_id, text="end🕴")
            # shuffle
            else:
                mapping_query = UserVocabularyMapping.select().join(User) \
                    .where((User.tgid == str(chat_id)) \
                           & (UserVocabularyMapping.check_times < self.COUNT_CHECK)) \
                    .order_by(fn.Random()).limit(1)
                if mapping_query.count() > 0:
                    mapping = mapping_query[0]
                    reply = str(mapping.vocabulary)
                    keyboard = [[InlineKeyboardButton("✅",
                                                      callback_data='{"command": "review", "type": "shuffle", "arg": %d, "check": 1}' % mapping.id),
                                 InlineKeyboardButton("⏭",
                                                      callback_data='{"command": "review", "type": "shuffle", "arg": %d, "check": 0}' % mapping.id), ]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    bot.send_message(chat_id=chat_id, text=reply, reply_markup=reply_markup)
                else:
                    bot.send_message(chat_id=chat_id, text="end🕴")

        elif data['command'] == 'test':
            if data['type'] == 'ask':
                try:
                    _id = data['arg']
                    word = Vocabulary.get(id=_id)
                except Vocabulary.DoesNotExist:
                    word = "oops!"

                keyboard = [[InlineKeyboardButton("⏭", callback_data='{"command": "test", "type": "next"}')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                bot.edit_message_text(text=str(word), chat_id=chat_id, message_id=query.message.message_id,
                                      reply_markup=reply_markup)
                if word != "oops!":
                    user, _ = User.get_or_create(tgid=str(chat_id))
                    mapping, new_created = UserVocabularyMapping.get_or_create(user=user, vocabulary=word)
                    if (not new_created) and mapping.check_times > 0:
                        mapping.update(check_times=0).execute()
            else:
                bot.edit_message_reply_markup(chat_id=chat_id, message_id=query.message.message_id)
                word = Vocabulary.select(Vocabulary.id, Vocabulary.word).order_by(fn.Random()).limit(1).first()
                reply = "Test:\n\t%s" % word.word
                keyboard = [[InlineKeyboardButton("❓",
                                                  callback_data='{"command": "test", "type": "ask", "arg": %d}' % word.id),
                             InlineKeyboardButton("⏭",
                                                  callback_data='{"command": "test", "type": "next"}')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                bot.send_message(chat_id=chat_id, text=reply, reply_markup=reply_markup)

        else:
            pass


if __name__ == '__main__':
    import os

    file_path = os.path.abspath(os.path.dirname(__file__))
    if not os.path.exists(os.path.join(file_path, "audio")):
        os.mkdir(os.path.join(file_path, "audio"))
    if not os.path.isfile(os.path.join(file_path, 'bot.db')):
        model_init()

    import config

    bot = WordBot(config.BOT_TOKEN)
    bot.run()
