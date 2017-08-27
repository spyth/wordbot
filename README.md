# wordbot
a telegram bot to learn vocabulary

## requirements
* [Python 3](https://www.python.org/)
* [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
* [peewee](http://docs.peewee-orm.com)
* [requests](http://docs.python-requests.org)
* [pytz](https://pypi.python.org/pypi/pytz)

## usage
* set your bot(you can get your own bot from [@BotFather](https://telegram.me/BotFather)) token in *config.py*. 
* install the requirements(recommend in [virtualenv](https://virtualenv.pypa.io)): `pip install -r requirements.txt`
* run the script: `python wordbot.py`

## bot usage
* send any word to the bot, it will response with the meaning of the word in **Chinese**.
* `/review` will review the word you have sent to the bot.
* `/test` will show the word without the meaning to test if you've remembered the meaning of the word.

## todo
* ~~add daily remind~~
