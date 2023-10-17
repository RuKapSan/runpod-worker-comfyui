import json
import time
import requests
import random

"""
This is the ComfyUI api prompt format.

If you want it for a specific workflow you can "enable dev mode options"
in the settings of the UI (gear beside the "Queue Size: ") this will enable
a button on the UI to save workflows in api format.

keep in mind ComfyUI is pre alpha software so this format will change a bit.

this is the one for the default workflow
"""

BASE_URI = "http://example.com"
FILENAME_PREFIX = "RUNPOD"

prompt_text = """
{{
    "3": {{
        "class_type": "KSampler",
        "inputs": {{
            "cfg": 8,
            "denoise": 1,
            "latent_image": [
                "5",
                0
            ],
            "model": [
                "4",
                0
            ],
            "negative": [
                "7",
                0
            ],
            "positive": [
                "6",
                0
            ],
            "sampler_name": "euler",
            "scheduler": "normal",
            "seed": 8566257,
            "steps": 20
        }}
    }},
    "4": {{
        "class_type": "CheckpointLoaderSimple",
        "inputs": {{
            "ckpt_name": "v1-5-pruned.safetensors"
        }}
    }},
    "5": {{
        "class_type": "EmptyLatentImage",
        "inputs": {{
            "batch_size": 1,
            "height": 512,
            "width": 512
        }}
    }},
    "6": {{
        "class_type": "CLIPTextEncode",
        "inputs": {{
            "clip": [
                "4",
                1
            ],
            "text": "masterpiece best quality girl"
        }}
    }},
    "7": {{
        "class_type": "CLIPTextEncode",
        "inputs": {{
            "clip": [
                "4",
                1
            ],
            "text": "bad hands"
        }}
    }},
    "8": {{
        "class_type": "VAEDecode",
        "inputs": {{
            "samples": [
                "3",
                0
            ],
            "vae": [
                "4",
                2
            ]
        }}
    }},
    "9": {{
        "class_type": "SaveImage",
        "inputs": {{
            "filename_prefix": "{FILENAME_PREFIX}",
            "images": [
                "8",
                0
            ]
        }}
    }}
}}
""".format(FILENAME_PREFIX=FILENAME_PREFIX)


def queue_prompt(prompt):
    return requests.post(
        f"{BASE_URI}/prompt",
        json={
            "prompt": prompt
        }
    )


if __name__ == "__main__":
    prompt = json.loads(prompt_text)
    # set the text prompt for our positive CLIPTextEncode
    prompt["6"]["inputs"]["text"] = "masterpiece best quality man wearing a hat"

    # set the seed for our KSampler node
    prompt["3"]["inputs"]["seed"] = random.randrange(1, 1000000)

    print('Queuing prompt')
    queue_response = queue_prompt(prompt)
    resp_json = queue_response.json()

    if queue_response.status_code == 200:
        prompt_id = resp_json['prompt_id']
        print(f'Prompt queued successfully: {prompt_id}')

        while True:
            print(f'Getting status of prompt: {prompt_id}')

            r = requests.get(
                f"{BASE_URI}/history/{prompt_id}"
            )

            resp_json = r.json()

            if r.status_code == 200 and len(resp_json):
                break

            time.sleep(1)

        print(r.status_code)

        print(json.dumps(resp_json, indent=4, default=str))
    else:
        print(f'ERROR: HTTP: {queue_response.status_code}')
        print(json.dumps(resp_json, indent=4, default=str))
