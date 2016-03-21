# coding: utf-8
from collections import defaultdict, namedtuple
from Queue import Queue
import logging
from threading import Thread
from smart_qq_bot.bot import QQBot

from smart_qq_bot.excpetions import (
    MsgProxyNotImplementError,
    InvalidHandlerType,
)
from smart_qq_bot.messages import MSG_TYPE_MAP

__all__ = (
    # functions
    "register",

    # objects
    "MessageObserver",
)


_registry = defaultdict(list)

RAW_TYPE = "raw_message"

MSG_TYPES = MSG_TYPE_MAP.keys()
MSG_TYPES.append(RAW_TYPE)


Handler = namedtuple("Handler", ("func", "name"))
Task = namedtuple("Task", ("func", "name"))


def register(func, msg_type=None, dispatcher_name=None):
    """
    Register handler to RAW if msg_type not given.
    :type func: callable
    :type msg_type: str or unicode
    """
    if msg_type and msg_type not in MSG_TYPE_MAP:
        raise InvalidHandlerType(
            "Invalid message type [%s]: type should be in %s"
            % (msg_type, str(MSG_TYPES))
        )
    handler = Handler(func=func, name=dispatcher_name)
    if msg_type is None:
        _registry[RAW_TYPE].append(handler)
    else:
        _registry[msg_type].append(handler)


class Worker(Thread):

    def __init__(
            self, queue, group=None,
            target=None, name=None, args=(),
            kwargs=None, verbose=None,
    ):
        """
        :type queue: Queue
        """
        super(Worker, self).__init__(
            group, target, name, args, kwargs, verbose
        )
        self.queue = queue
        self._stopped = False
        self.worker_timeout = 20
        self._stop_done = False

    def run(self):
        while True:
            if self._stopped:
                break
            task = self.queue.get()
            try:
                task.func()
            except Exception:
                logging.exception(
                    "Error occurs when running task from plugin [%s]."
                    % task.name
                )
        self._stop_done = True

    def stop(self):
        self._stopped = True


class MessageObserver(object):

    _registry = _registry

    def __init__(self, bot, workers=5):
        """
        :type bot: smart_qq_bot.bot.QQBot
        """
        if not isinstance(bot, QQBot):
            raise MsgProxyNotImplementError(
                "bot should be instance of QQBot"
            )
        self.bot = bot
        self.handler_queue = Queue()
        self.workers = [Worker(self.handler_queue) for i in xrange(workers)]
        for worker in self.workers:
            worker.setDaemon(True)
            worker.start()

    def handle_msg_list(self, msg_list):
        """
        :type msg_list: list or tuple
        """
        for msg in msg_list:
            self._handle_one(msg)

    def _handle_one(self, msg):
        """
        :type msg: smart_qq_bot.messages.QMessage
        """
        handlers = self._registry[msg.type]

        for handler in handlers + self._registry[RAW_TYPE]:
            def task():
                return handler.func(msg=msg, bot=self.bot)
            self.handler_queue.put(Task(func=task, name=handler.name))