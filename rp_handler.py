import time
import requests
import runpod
from runpod.serverless.modules.rp_logger import RunPodLogger
from requests.adapters import HTTPAdapter, Retry


BASE_URL = 'http://127.0.0.1:3000'
TIMEOUT = 600

session = requests.Session()
retries = Retry(total=10, backoff_factor=0.1, status_forcelist=[502, 503, 504])
session.mount('http://', HTTPAdapter(max_retries=retries))
logger = RunPodLogger()


# ---------------------------------------------------------------------------- #
#                               ComfyUI Functions                              #
# ---------------------------------------------------------------------------- #

def wait_for_service(url):
    retries = 0

    while True:
        try:
            requests.get(url)
            return
        except requests.exceptions.RequestException:
            retries += 1

            # Only log every 15 retries so the logs don't get spammed
            if retries % 15 == 0:
                logger.info('Service not ready yet. Retrying...')
        except Exception as err:
            logger.error(f'Error: {err}')

        time.sleep(0.2)


def send_get_request(endpoint):
    return session.get(
        url=f'{BASE_URL}/{endpoint}',
        timeout=TIMEOUT
    )


def send_post_request(endpoint, payload):
    return session.post(
        url=f'{BASE_URL}/{endpoint}',
        json=payload,
        timeout=TIMEOUT
    )


# ---------------------------------------------------------------------------- #
#                                RunPod Handler                                #
# ---------------------------------------------------------------------------- #
def handler(event):
    # TODO: Implement
    pass


if __name__ == "__main__":
    wait_for_service(url='http://127.0.0.1:3000/system_stats')
    logger.log('ComfyUI API is ready', 'INFO')
    logger.log('Starting RunPod Serverless...', 'INFO')
    runpod.serverless.start(
        {
            'handler': handler
        }
    )
    runpod.create_pod()