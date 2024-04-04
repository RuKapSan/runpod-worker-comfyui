from random import randint
import time
import uuid
import requests
import traceback
import json
import base64

import websocket
import runpod
from runpod.serverless.utils.rp_validator import validate
from runpod.serverless.modules.rp_logger import RunPodLogger
from requests.adapters import HTTPAdapter, Retry
from schemas.input import INPUT_SCHEMA
from comfy_api_simplified import ComfyApiWrapper, ComfyWorkflowWrapper


BASE_URI = 'http://127.0.0.1:3000'
VOLUME_MOUNT_PATH = '/runpod-volume'
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
        url=f'{BASE_URI}/{endpoint}',
        timeout=TIMEOUT
    )

def new_queue_prompt_and_wait(self, prompt: dict) -> str:
    client_id = str(uuid.uuid4())
    resp = self.queue_prompt(prompt, client_id)
    print(resp)
    prompt_id = resp["prompt_id"]
    print(f"Connecting to {self.ws_url.format(client_id).split('@')[-1]}")
    
    ws = websocket.create_connection(self.ws_url.format(client_id))
    try:
        while True:
            out = ws.recv()
            if isinstance(out, str):
                message = json.loads(out)
                print(message)  # Предполагается, что у вас есть настроенный логгер
                if message["type"] == "crystools.monitor":
                    continue
                if message["type"] == "execution_error":
                    data = message["data"]
                    if data["prompt_id"] == prompt_id:
                        raise Exception("Execution error occurred.")
                if message["type"] == "status":
                    data = message["data"]
                    if data["status"]["exec_info"]["queue_remaining"] == 0:
                        return prompt_id
                if message["type"] == "executing":
                    data = message["data"]
                    if data["node"] is None and data["prompt_id"] == prompt_id:
                        return prompt_id
    finally:
        ws.close()

def new_queue_and_wait_images(self, prompt: dict, output_node_title: str) -> dict:
    # Предполагается, что вы уже определили метод get_history и get_image соответствующим образом.
    prompt_id = self.queue_prompt_and_wait(prompt)
    history = self.get_history(prompt_id)
    image_node_id = prompt.get_node_id(output_node_title)
    images = history[prompt_id]["outputs"][image_node_id]["images"]
    return {
        image["filename"]: self.get_image(
            image["filename"], image["subfolder"], image["type"]
        )
        for image in images
    }


def send_post_request(payload):
    
    api = ComfyApiWrapper(BASE_URI)

    api.queue_and_wait_images = new_queue_and_wait_images.__get__(api, ComfyApiWrapper)
    api.queue_prompt_and_wait = new_queue_prompt_and_wait.__get__(api, ComfyApiWrapper)


    results = api.queue_and_wait_images(payload, "Image Save")

    for filename, image_bytes in results.items():
        image_bytes = image_bytes
    
    return image_bytes

def get_txt2img_payload(workflow, payload):
    workflow.set_node_param("KSampler", "seed", randint(0, 1000000))
    logger.debug(payload)
    logger.debug(type(payload))
    for value in payload.keys():
        workflow.set_node_param(value, "Text", payload[value])
    return workflow


def get_img2img_payload(workflow, payload):
    workflow["13"]["inputs"]["seed"] = payload["seed"]
    workflow["13"]["inputs"]["steps"] = payload["steps"]
    workflow["13"]["inputs"]["cfg"] = payload["cfg_scale"]
    workflow["13"]["inputs"]["sampler_name"] = payload["sampler_name"]
    workflow["13"]["inputs"]["scheduler"] = payload["scheduler"]
    workflow["13"]["inputs"]["denoise"] = payload["denoise"]
    workflow["1"]["inputs"]["ckpt_name"] = payload["ckpt_name"]
    workflow["2"]["inputs"]["width"] = payload["width"]
    workflow["2"]["inputs"]["height"] = payload["height"]
    workflow["2"]["inputs"]["target_width"] = payload["width"]
    workflow["2"]["inputs"]["target_height"] = payload["height"]
    workflow["4"]["inputs"]["width"] = payload["width"]
    workflow["4"]["inputs"]["height"] = payload["height"]
    workflow["4"]["inputs"]["target_width"] = payload["width"]
    workflow["4"]["inputs"]["target_height"] = payload["height"]
    workflow["6"]["inputs"]["text"] = payload["prompt"]
    workflow["7"]["inputs"]["text"] = payload["negative_prompt"]
    return workflow


def get_workflow_payload(workflow_name, payload):

    workflow = ComfyWorkflowWrapper(f'/workspace/workflows/{workflow_name}.json')

    if workflow_name == 'txt2img':
        workflow = get_txt2img_payload(workflow, payload)

    return workflow


def get_filenames(output):
    for key, value in output.items():
        if 'images' in value and isinstance(value['images'], list):
            return value['images']


# ---------------------------------------------------------------------------- #
#                                RunPod Handler                                #
# ---------------------------------------------------------------------------- #
def handler(event):
    job_id = event['id']

    try:
        validated_input = validate(event['input'], INPUT_SCHEMA)

        if 'errors' in validated_input:
            return {
                'error': '\n'.join(validated_input['errors'])
            }

        payload = validated_input['validated_input']
        workflow_name = payload['workflow']
        payload = payload['payload']

        if workflow_name == 'default':
            workflow_name = 'txt2img'

        logger.info(f'Workflow: {workflow_name}', job_id)

        if workflow_name != 'custom':
            try:
                payload = get_workflow_payload(workflow_name, payload)
            except Exception as e:
                logger.error(f'Unable to load workflow payload for: {workflow_name}', job_id)
                raise

        logger.debug('Queuing prompt')

        response = send_post_request(payload)

        image=base64.b64encode(response).decode("utf-8")

        return {
            'image': image
        }
    
    except Exception as e:
        logger.error(f'An exception was raised: {e}', job_id)

        return {
            'error': traceback.format_exc(),
            'refresh_worker': True
        }


if __name__ == '__main__':
    wait_for_service(url=f'{BASE_URI}/system_stats')
    logger.info('ComfyUI API is ready')
    logger.info('Starting RunPod Serverless...')
    runpod.serverless.start(
        {
            'handler': handler
        }
    )
