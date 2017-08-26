import datetime

from peewee import (SqliteDatabase, Model, BooleanField, CharField,
                    DateTimeField, ForeignKeyField, IntegerField)

db = SqliteDatabase('bot.db')


class BaseModel(Model):
    class Meta:
        database = db


class Vocabulary(BaseModel):
    word = CharField(unique=True)
    pronunciation = CharField()
    definition = CharField(max_length=1023)
    audio = CharField(null=True)

    def __str__(self):
        represent = '{word}\n\n[{pronunciation}]\n{definition}\n'.format(word=self.word,
                                                                       pronunciation=self.pronunciation,
                                                                       definition=self.definition)
        return represent


class User(BaseModel):
    tgid = CharField(unique=True)
    is_subscribe = BooleanField(default=False)
    created_date = DateTimeField(default=datetime.datetime.now)


class UserVocabularyMapping(BaseModel):
    vocabulary = ForeignKeyField(Vocabulary)
    user = ForeignKeyField(User)
    check_times = IntegerField(default=0)

def init():
    db.create_tables([Vocabulary, User, UserVocabularyMapping])


if __name__ == '__main__':
    init()
