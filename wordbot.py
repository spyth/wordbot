import logging
import json
from datetime import datetime

from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters,
                          Job, CallbackQueryHandler)
from telegram import (ChatAction, ParseMode, InlineKeyboardButton, InlineKeyboardMarkup)
from peewee import fn
import pytz

from word import word_query
from model import User, UserVocabularyMapping, Vocabulary, init as model_init

logger = logging.getLogger(__name__)


class WordBot(object):
    def __init__(self, BOT_TOKEN, COUNT_CHECK=5, timezone='Asia/Hong_Kong', notify_time='23:00'):
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

        # add daily reminder
        if notify_time:
            try:
                tz = pytz.timezone(timezone)
                utc_now = pytz.utc.localize(datetime.utcnow())
                tz_now = utc_now.astimezone(tz)
                hour, minute = tuple(map(int, notify_time.split(':')))
                expect_time = tz_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                delay = (int((expect_time - tz_now).total_seconds()) + 24 * 60 * 60) % (24 * 60 * 60)
                self.updater.job_queue.run_daily(self.daily_remind, time=delay)
            except:
                logger.warning('oops, daily reminder start failed!')
                raise

    def run(self):
        self.updater.start_polling()
        self.updater.idle()

    @staticmethod
    def daily_remind(bot, job):
        for u in User.select():
            bot.send_message(chat_id=u.tgid, text="👩‍🏫 Would you like to /review or /test vocabulary?")

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
            response = '👽 500'
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
        # bot.sendChatAction(chat_id=update.message.chat_id, action=ChatAction.TYPING)
        word = Vocabulary.select(Vocabulary.id, Vocabulary.word).order_by(fn.Random()).limit(1).first()
        reply = "**%s**?" % word.word
        keyboard = [[InlineKeyboardButton("❓",
                                          callback_data='{"command": "test", "type": "ask", "arg": %d}' % word.id),
                     InlineKeyboardButton("✅",
                                          callback_data='{"command": "test", "type": "check", "arg": %d}' % word.id)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        bot.send_message(chat_id=update.message.chat_id, text=reply,
                         reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

    def reply_button_callback(self, bot, update):
        query = update.callback_query
        chat_id = query.message.chat_id

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
            # bot.sendChatAction(chat_id=chat_id, action=ChatAction.TYPING)
            _id = data['arg']

            if data['check'] == 1:
                UserVocabularyMapping.update(check_times=UserVocabularyMapping.check_times + 1) \
                    .where(UserVocabularyMapping.id == _id).execute()
                mapping = UserVocabularyMapping.get(id=_id)
                if mapping.check_times >= self.COUNT_CHECK:
                    reply_text = str(mapping.vocabulary) + '\n' + '🎉' * self.COUNT_CHECK
                else:
                    reply_text = str(mapping.vocabulary) + '\n' + '⭐️' * mapping.check_times
                bot.edit_message_text(text=reply_text, chat_id=chat_id, message_id=query.message.message_id)
            else:
                # clear the previous reply button
                bot.edit_message_reply_markup(chat_id=chat_id, message_id=query.message.message_id)

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
            if data['type'] == 'next':
                bot.edit_message_reply_markup(chat_id=chat_id, message_id=query.message.message_id)
                self.test(bot, query)
            else:
                try:
                    _id = data['arg']
                    word = Vocabulary.get(id=_id)
                except Vocabulary.DoesNotExist:
                    bot.edit_message_text(text='oops!', chat_id=chat_id, message_id=query.message.message_id)
                    return
                user, _ = User.get_or_create(tgid=str(chat_id))
                mapping, new_created = UserVocabularyMapping.get_or_create(user=user, vocabulary=word)
                if data['type'] == 'check':
                    extra_msg = '\n' + '⭐️' * (mapping.check_times + 1)
                    UserVocabularyMapping.update(check_times=UserVocabularyMapping.check_times + 1) \
                        .where(UserVocabularyMapping.id == mapping.id).execute()
                else:
                    extra_msg = '\n' + '😆'
                    if (not new_created) and mapping.check_times > 0:
                        UserVocabularyMapping.update(check_times=0).where(
                            UserVocabularyMapping.id == mapping.id).execute()

                keyboard = [[InlineKeyboardButton("⏭", callback_data='{"command": "test", "type": "next"}')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                bot.edit_message_text(text=str(word) + extra_msg, chat_id=chat_id,
                                      message_id=query.message.message_id, reply_markup=reply_markup)

        else:
            pass


if __name__ == '__main__':
    logging.basicConfig(filename='spam.log',
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
    import os
    file_path = os.path.abspath(os.path.dirname(__file__))
    if not os.path.exists(os.path.join(file_path, "audio")):
        os.mkdir(os.path.join(file_path, "audio"))
    if not os.path.isfile(os.path.join(file_path, 'bot.db')):
        model_init()

    import config
    bot = WordBot(config.BOT_TOKEN, timezone=config.TIMEZONE, notify_time=config.NOTIFY_TIME)
    bot.run()
