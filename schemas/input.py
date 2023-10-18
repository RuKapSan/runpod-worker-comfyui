INPUT_SCHEMA = {
    'workflow': {
        'type': str,
        'required': False,
        'default': 'txt2img',
        'constraints': lambda workflow: workflow in [
            'default',
            'txt2img',
            'custom'
        ]
    },
    'payload': {
        'type': dict,
        'required': True
    }
}
