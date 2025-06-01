import asyncio
from threading import Thread
from queue import ShutDown, Empty, Queue
from typing import Coroutine, Any


class ConnectorThread(Thread):
    """
    Connector's thread. Handles async tasks and returns the result.
    """
    def __init__(self, tasks_input_queue: Queue, results_output_queue: Queue):
        super().__init__()
        self._tasks_input_queue = tasks_input_queue
        self._results_output_queue = results_output_queue
        self._asyncio_loop = asyncio.new_event_loop()

    def run(self) -> None:
        """
        Thread's control loop: retrieve one task at a time to
         execute it and return its result using the two queues.

        The thread stops its execution when at least one queue gets closed.
        """
        try:
            while True:
                try:
                    async_task = self._tasks_input_queue.get(True, 0.1)
                    task_result = self.compute_task(async_task)
                    self._results_output_queue.put(task_result)
                    self._tasks_input_queue.task_done()
                    self._results_output_queue.join()
                except Empty:
                    # the timeout expired
                    pass
        except ShutDown:
            # a queue was closed
            pass

    def compute_task(self, task: Coroutine) -> Any:
        """
        Execute the async task using asyncio's loop
        and return the result.
        """
        return self._asyncio_loop.run_until_complete(task)
