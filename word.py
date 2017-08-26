import os
import logging

import requests

from model import Vocabulary

logger = logging.getLogger(__name__)


class ShanbayAPI(object):
    @classmethod
    def query_api(cls, word):
        _json = dict()
        try:
            with requests.Session() as s:
                s.headers.update({'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.101 Safari/537.36'})
                resp = s.get('https://api.shanbay.com/bdc/search/?word=%s' % word)
        except Exception as ex:
            logger.warning(ex)
        else:
            try:
                _json = resp.json()
            except:
                logger.warning(resp.content)
        return cls.de_json(_json)

    @staticmethod
    def de_json(resp):
        data = dict()
        try:
            if resp['status_code'] == 0:
                data['word'] = resp['data']['content']
                data['definition'] = resp['data']['definition']
                data['pronunciation'] = resp['data']['pronunciation']
                if resp['data']['audio']:
                    try:
                        s = requests.Session()
                        s.headers.update({'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.101 Safari/537.36'})
                        audio_resp = s.get(resp['data']['audio'])
                        idx = resp['data']['audio'].rfind('/')
                        file_path = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                                 "audio", resp['data']['audio'][idx+1:]))
                        open(file_path, 'wb').write(audio_resp.content)
                        data['audio'] = file_path
                    except Exception as ex:
                        logger.warning(ex)
                data['success'] = 1
                return data
        except:
            pass
        logger.warning(resp)
        data['success'] = 0
        return data



def word_query(word):
    _word = word.strip()
    res = None
    if _word.isalpha():
        if not _word.isupper():
            _word = _word.lower()
        try:
            res = Vocabulary.get(Vocabulary.word==_word)
        except Vocabulary.DoesNotExist:
            query_res = ShanbayAPI.query_api(_word)
            if query_res['success'] > 0:
                res = Vocabulary.create(**query_res)
        return res
    return res


if __name__ == '__main__':
    pass
