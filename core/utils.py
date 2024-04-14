from functools import wraps

from faker import Faker


def generate_trace_phrase():
    """
    Human-friendly trace phrase generator.
    Does not guarantee being unique, but can be memorized without copy-pasting
    """
    faker = Faker()

    subject_definition = faker.word(ext_word_list=None, part_of_speech="adjective")
    subject = faker.word(ext_word_list=None, part_of_speech="noun")
    predicate = faker.word(ext_word_list=None, part_of_speech="verb")
    object_ = faker.word(ext_word_list=None, part_of_speech="noun")

    return f"{subject_definition} {subject} {predicate} {object_}"


def singleton(cls):
    class _Wrapper(cls):
        __instance = None

        def __new__(cls, *args, **kwargs):
            if _Wrapper.__instance is None:
                instance = super().__new__(cls, *args, **kwargs)
                cls.__init__(instance, *args, **kwargs)
                _Wrapper.__instance = instance
            return _Wrapper.__instance

    return _Wrapper
