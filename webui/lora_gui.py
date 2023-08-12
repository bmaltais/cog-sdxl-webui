# v1: initial release
# v2: add open and save folder icons
# v3: Add new Utilities tab for Dreambooth folder preparation
# v3.1: Adding captionning of images to utilities

import gradio as gr
import json
import math
import os
import subprocess
import psutil
import pathlib
import argparse
from datetime import datetime
from library.common_gui import (
    get_file_path,
    get_any_file_path,
    get_saveasfile_path,
    color_aug_changed,
    save_inference_file,
    run_cmd_advanced_training,
    run_cmd_training,
    update_my_data,
    check_if_model_exist,
    output_message,
    verify_image_folder_pattern,
    SaveConfigFile,
    save_to_file,
    check_duplicate_filenames
)
from library.class_configuration_file import ConfigurationFile
# from library.class_source_model import SourceModel
from library.class_basic_training import BasicTraining
from library.class_advanced_training import AdvancedTraining
from library.class_sdxl_parameters import SDXLParameters
from library.class_folders import Folders
from library.class_command_executor import CommandExecutor
from library.tensorboard_gui import (
    gradio_tensorboard,
    start_tensorboard,
    stop_tensorboard,
)
from library.utilities import utilities_tab
from library.class_sample_images import SampleImages, run_cmd_sample
from library.class_lora_tab import LoRATools

from library.custom_logging import setup_logging

# Set up logging
log = setup_logging()

# Setup command executor
executor = CommandExecutor()

button_run = gr.Button('Start training', variant='primary')
            
button_stop_training = gr.Button('Stop training')

document_symbol = '\U0001F4C4'   # 📄

def save_configuration(
    save_as,
    file_path,
    caption_prefix,
    checkpointing_steps,
    clipseg_temperature,
    crop_based_on_salience,
    debug,
    input_images,
    is_lora,
    lora_lr,
    lora_rank,
    lr_scheduler,
    lr_warmup_steps,
    mask_target_prompts,
    max_train_steps,
    num_train_epochs,
    resolution,
    token_string,
    use_face_detection_instead,
    seed,
    ti_lr,
    train_batch_size,
    unet_learning_rate,
    verbose,
):
    # Get list of function parameters and values
    parameters = list(locals().items())

    original_file_path = file_path

    save_as_bool = True if save_as.get('label') == 'True' else False

    if save_as_bool:
        log.info('Save as...')
        file_path = get_saveasfile_path(file_path)
    else:
        log.info('Save...')
        if file_path == None or file_path == '':
            file_path = get_saveasfile_path(file_path)

    # log.info(file_path)

    if file_path == None or file_path == '':
        return original_file_path  # In case a file_path was provided and the user decide to cancel the open action

    # Extract the destination directory from the file path
    destination_directory = os.path.dirname(file_path)

    # Create the destination directory if it doesn't exist
    if not os.path.exists(destination_directory):
        os.makedirs(destination_directory)

    SaveConfigFile(parameters=parameters, file_path=file_path, exclusion=['file_path', 'save_as'])

    return file_path


def open_configuration(
    ask_for_file,
    apply_preset,
    file_path,
    caption_prefix,
    checkpointing_steps,
    clipseg_temperature,
    crop_based_on_salience,
    debug,
    input_images,
    is_lora,
    lora_lr,
    lora_rank,
    lr_scheduler,
    lr_warmup_steps,
    mask_target_prompts,
    max_train_steps,
    num_train_epochs,
    resolution,
    token_string,
    use_face_detection_instead,
    seed,
    ti_lr,
    train_batch_size,
    unet_learning_rate,
    verbose,
    training_preset,
):
    # Get list of function parameters and values
    parameters = list(locals().items())

    ask_for_file = True if ask_for_file.get('label') == 'True' else False
    apply_preset = True if apply_preset.get('label') == 'True' else False

    # Check if we are "applying" a preset or a config
    if apply_preset:
        log.info(f'Applying preset {training_preset}...')
        file_path = f'./presets/lora/{training_preset}.json'
    else:
        # If not applying a preset, set the `training_preset` field to an empty string
        # Find the index of the `training_preset` parameter using the `index()` method
        training_preset_index = parameters.index(
            ('training_preset', training_preset)
        )

        # Update the value of `training_preset` by directly assigning an empty string value
        parameters[training_preset_index] = ('training_preset', '')

    original_file_path = file_path

    if ask_for_file:
        file_path = get_file_path(file_path)

    if not file_path == '' and not file_path == None:
        # Load variables from JSON file
        with open(file_path, 'r') as f:
            my_data = json.load(f)
            log.info('Loading config...')

            # Update values to fix deprecated options, set appropriate optimizer if it is set to True, etc.
            my_data = update_my_data(my_data)
    else:
        file_path = original_file_path  # In case a file_path was provided and the user decides to cancel the open action
        my_data = {}

    values = [file_path]
    for key, value in parameters:
        # Set the value in the dictionary to the corresponding value in `my_data`, or the default value if not found
        if not key in ['ask_for_file', 'apply_preset', 'file_path']:
            json_value = my_data.get(key)
            values.append(json_value if json_value is not None else value)

    return tuple(values)


def train_model(
    headless,
    print_only,
    caption_prefix,
    checkpointing_steps,
    clipseg_temperature,
    crop_based_on_salience,
    debug,
    input_images,
    is_lora,
    lora_lr,
    lora_rank,
    lr_scheduler,
    lr_warmup_steps,
    mask_target_prompts,
    max_train_steps,
    num_train_epochs,
    resolution,
    token_string,
    use_face_detection_instead,
    seed,
    ti_lr,
    train_batch_size,
    unet_learning_rate,
    verbose,
):
    # Get list of function parameters and values
    parameters = list(locals().items())
    global command_running
    
    print_only_bool = True if print_only.get('label') == 'True' else False
    log.info(f'Start training COG LoRA...')
    headless_bool = True if headless.get('label') == 'True' else False

    if input_images == '':
        output_message(
            msg='Image file archive missing', headless=headless_bool
        )
        return

    if not os.path.exists(input_images):
        output_message(
            msg='Image file archive cannot be found', headless=headless_bool
        )
        return

    run_cmd = f'cog train'
    run_cmd += f' -i "caption_prefix={caption_prefix}"'
    run_cmd += f' -i checkpointing_steps={checkpointing_steps}'
    run_cmd += f' -i clipseg_temperature={clipseg_temperature}'
    if crop_based_on_salience:
        run_cmd += f' -i crop_based_on_salience=True'
    else: 
        run_cmd += f' -i crop_based_on_salience=False'
    
    if is_lora:
        run_cmd += f' -i is_lora=True'
    else: 
        run_cmd += f' -i is_lora=False'
    run_cmd += f' -i clipseg_temperature={clipseg_temperature}'
    run_cmd += f' -i lora_lr={lora_lr}'
    run_cmd += f' -i lora_rank={lora_rank}'
    run_cmd += f' -i lr_scheduler={lr_scheduler}'
    run_cmd += f' -i lr_warmup_steps={lr_warmup_steps}'
    if not mask_target_prompts == '':
        run_cmd += f' -i "mask_target_prompts={mask_target_prompts}"'
    run_cmd += f' -i max_train_steps={max_train_steps}'
    run_cmd += f' -i num_train_epochs={num_train_epochs}'
    run_cmd += f' -i resolution={resolution}'
    run_cmd += f' -i "token_string={token_string}"'
    run_cmd += f' -i "input_images=@{input_images}"'
    if use_face_detection_instead:
        run_cmd += f' -i use_face_detection_instead=True'
    else:
        run_cmd += f' -i use_face_detection_instead=False'
    run_cmd += f' -i seed={seed}'
    run_cmd += f' -i ti_lr={ti_lr}'
    run_cmd += f' -i train_batch_size={train_batch_size}'
    run_cmd += f' -i unet_learning_rate={unet_learning_rate}'
    if verbose:
        run_cmd += f' -i verbose=True'
    else:
        run_cmd += f' -i verbose=False'
    if debug:
        run_cmd += f' --debug'
    
    
    

    if print_only_bool:
        log.warning(
            'Here is the trainer command as a reference. It will not be executed:\n'
        )
        print(run_cmd)
        
        save_to_file(run_cmd)
    else:
        # Saving config file for model
        current_datetime = datetime.now()
        formatted_datetime = current_datetime.strftime("%Y%m%d-%H%M%S")
        log.info(run_cmd)
        # Run the command
        executor.execute_command(run_cmd=run_cmd)


def lora_tab(
    train_data_dir_input=gr.Textbox(),
    reg_data_dir_input=gr.Textbox(),
    output_dir_input=gr.Textbox(),
    logging_dir_input=gr.Textbox(),
    headless=False,
):
    dummy_db_true = gr.Label(value=True, visible=False)
    dummy_db_false = gr.Label(value=False, visible=False)
    dummy_headless = gr.Label(value=headless, visible=False)

    with gr.Tab('Training'):
        gr.Markdown(
            'Train a custom model using cog trainer LoRA python code...'
        )
        
        # Setup Configuration Files Gradio
        config = ConfigurationFile(headless)

        with gr.Tab('Folders'):
            folders = Folders(headless=headless)
            
        with gr.Tab('Parameters'):
            def list_presets(path):
                json_files = []
                
                for file in os.listdir(path):
                    if file.endswith('.json'):
                        json_files.append(os.path.splitext(file)[0])
                        
                user_presets_path = os.path.join(path, 'user_presets')
                if os.path.isdir(user_presets_path):
                    for file in os.listdir(user_presets_path):
                        if file.endswith('.json'):
                            preset_name = os.path.splitext(file)[0]
                            json_files.append(os.path.join('user_presets', preset_name))
                
                return json_files
            
            training_preset = gr.Dropdown(
                label='Presets',
                choices=list_presets('./presets/lora'),
                elem_id='myDropdown',
            )
            
            with gr.Row():
                seed = gr.Number(
                    label='Seed', value=1337,
                    info='Random seed for reproducible training. Leave empty to use a random seed',
                    minimum=0, precision=0,
                )
                resolution = gr.Number(
                    label='Resolution', value=768,
                    info='Square pixel resolution which your images will be resized to for training',
                    minimum=128, precision=0,maximum=4096
                )
                train_batch_size = gr.Slider(
                    label='Train batch size', value=4,
                    info='Batch size (per device) for training',
                    minimum=1, step=1, maximum=64
                )
            with gr.Row():
                num_train_epochs = gr.Number(
                    label='Number of epoch', value=4000,
                    info='Number of epochs to loop through your training dataset',
                    minimum=1, precision=0,
                )
                max_train_steps = gr.Number(
                    label='Max number of steps', value=1000,
                    info='Number of individual training steps. Takes precedence over num_train_epochs',
                    minimum=1, precision=0,
                )
                checkpointing_steps = gr.Number(
                    label='Checkpointing steps', value=999999,
                    info='Number of steps between saving checkpoints. Set to very very high number to disable checkpointing, because you don\'t need one.',
                    minimum=1, precision=0,
                )
            with gr.Row():
                is_lora = gr.Checkbox(
                    label='LoRA',
                    value=True,
                    info='Whether to use LoRA training. If set to False, will use Full fine tuning',
                )
                unet_learning_rate = gr.Number(
                    label='UNet learning rate', value=1e-6,
                    info='Learning rate for the U-Net. We recommend this value to be somewhere between `1e-6` to `1e-5`.',
                    minimum=1e-8, maximum=1
                )
                ti_lr = gr.Number(
                    label='TI learning rate', value=3e-4,
                    info='Scaling of learning rate for training textual inversion embeddings. Don\'t alter unless you know what you\'re doing.',
                    minimum=1e-8, maximum=1
                )
                lora_lr = gr.Number(
                    label='LoRA learning rate', value=1e-4,
                    info='Scaling of learning rate for training LoRA embeddings. Don\'t alter unless you know what you\'re doing.',
                    minimum=1e-8, maximum=1
                )
            with gr.Row():
                lora_rank = gr.Slider(
                    label='LoRA rank', value=32,
                    info='Rank of LoRA embeddings. Don\'t alter unless you know what you\'re doing.',
                    minimum=1, step=1, maximum=512
                )
                lr_scheduler = gr.Dropdown(
                    label='LR Scheduler',
                    choices=[
                        'constant',
                        'linear',
                    ],
                    value='constant',
                    info='Learning rate scheduler to use for training',
                )
                lr_warmup_steps = gr.Number(
                    label='LR warmup steps', value=100,
                    info='Number of warmup steps for lr schedulers with warmups.',
                    minimum=0, precision=0,
                )
            with gr.Row():
                token_string = gr.Textbox(
                    label='Token string', value='TOK',
                    info='A unique string that will be trained to refer to the concept in the input images. Can be anything, but TOK works well'
                )
                
                caption_prefix = gr.Textbox(
                    label='Caption prefix', value='a photo of TOK, ',
                    info='Text which will be used as prefix during automatic captioning. Must contain the `token_string`. For example, if caption text is \'a photo of TOK\', automatic captioning will expand to \'a photo of TOK under a bridge\', \'a photo of TOK holding a cup\', etc.'
                )
            with gr.Row():
                mask_target_prompts = gr.Textbox(
                    label='Mask target prompts', placeholder='(Optional)',
                    info='Prompt that describes part of the image that you will find important. For example, if you are fine-tuning your pet, `photo of a dog` will be a good prompt. Prompt-based masking is used to focus the fine-tuning process on the important/salient parts of the image',
                )
                crop_based_on_salience = gr.Checkbox(
                    label='Crop based on salience',
                    value=True,
                    info='If you want to crop the image to `target_size` based on the important parts of the image, set this to True. If you want to crop the image based on face detection, set this to False',
                )
                use_face_detection_instead = gr.Checkbox(
                    label='use_face_detection_instead',
                    value=False,
                    info='If you want to use face detection instead of CLIPSeg for masking. For face applications, we recommend using this option.',
                )
            with gr.Row():
                clipseg_temperature = gr.Number(
                    label='ClipSEG temperature', value=1.0,
                    info='How blurry you want the CLIPSeg mask to be. We recommend this value be something between `0.5` to `1.0`. If you want to have more sharp mask \(but thus more errorful\), you can decrease this value.',
                    minimum=0.0, maximum=1.0, precision=2,
                )
                verbose = gr.Checkbox(
                    label='Verbose',
                    value=True,
                    info='Verbose output.',
                )
                debug = gr.Checkbox(
                    label='Debug',
                    value=False,
                    info='Get debut output while training.',
                )
        with gr.Row():
            button_run = gr.Button('Start training', variant='primary')
            
            button_stop_training = gr.Button('Stop training')

        button_print = gr.Button('Print training command')

        # Setup gradio tensorboard buttons
        button_start_tensorboard, button_stop_tensorboard = gradio_tensorboard()

        button_start_tensorboard.click(
            start_tensorboard,
            inputs=folders.logging_dir,
            show_progress=False,
        )

        button_stop_tensorboard.click(
            stop_tensorboard,
            show_progress=False,
        )

        settings_list = [
            caption_prefix,
            checkpointing_steps,
            clipseg_temperature,
            crop_based_on_salience,
            debug,
            folders.train_data_dir,
            is_lora,
            lora_lr,
            lora_rank,
            lr_scheduler,
            lr_warmup_steps,
            mask_target_prompts,
            max_train_steps,
            num_train_epochs,
            resolution,
            token_string,
            use_face_detection_instead,
            seed,
            ti_lr,
            train_batch_size,
            unet_learning_rate,
            verbose,
        ]

        config.button_open_config.click(
            open_configuration,
            inputs=[dummy_db_true, dummy_db_false, config.config_file_name]
            + settings_list
            + [training_preset],
            outputs=[config.config_file_name]
            + settings_list
            + [training_preset],
            show_progress=False,
        )

        config.button_load_config.click(
            open_configuration,
            inputs=[dummy_db_false, dummy_db_false, config.config_file_name]
            + settings_list
            + [training_preset],
            outputs=[config.config_file_name]
            + settings_list
            + [training_preset],
            show_progress=False,
        )

        training_preset.input(
            open_configuration,
            inputs=[dummy_db_false, dummy_db_true, config.config_file_name]
            + settings_list
            + [training_preset],
            outputs=[gr.Textbox()] + settings_list + [training_preset],
            show_progress=False,
        )

        config.button_save_config.click(
            save_configuration,
            inputs=[dummy_db_false, config.config_file_name] + settings_list,
            outputs=[config.config_file_name],
            show_progress=False,
        )

        config.button_save_as_config.click(
            save_configuration,
            inputs=[dummy_db_true, config.config_file_name] + settings_list,
            outputs=[config.config_file_name],
            show_progress=False,
        )

        button_run.click(
            train_model,
            inputs=[dummy_headless] + [dummy_db_false] + settings_list,
            show_progress=False,
        )
        
        button_stop_training.click(
            executor.kill_command
        )

        button_print.click(
            train_model,
            inputs=[dummy_headless] + [dummy_db_true] + settings_list,
            show_progress=False,
        )
        
    # with gr.Tab('Tools'):
    #     lora_tools = LoRATools(folders=folders, headless=headless)
        
    # with gr.Tab('Guides'):
    #     gr.Markdown(
    #         'This section provide Various LoRA guides and information...'
    #     )
    #     # if os.path.exists('./docs/LoRA/top_level.md'):
    #     #     with open(os.path.join('./docs/LoRA/top_level.md'), 'r', encoding='utf8') as file:
    #     #         guides_top_level = file.read() + '\n'
    #     # gr.Markdown(guides_top_level)

    return (
        folders.train_data_dir,
        folders.reg_data_dir,
        folders.output_dir,
        folders.logging_dir,
    )


def UI(**kwargs):
    try:
        # Your main code goes here
        while True:
            css = ''

            headless = kwargs.get('headless', False)
            log.info(f'headless: {headless}')

            if os.path.exists('./webui/style.css'):
                with open(os.path.join('./webui/style.css'), 'r', encoding='utf8') as file:
                    log.info('Load CSS...')
                    css += file.read() + '\n'

            interface = gr.Blocks(
                css=css, title='Kohya_ss GUI', theme=gr.themes.Default()
            )

            with interface:
                with gr.Tab('COG LoRA Trainer'):
                    (
                        train_data_dir_input,
                        reg_data_dir_input,
                        output_dir_input,
                        logging_dir_input,
                    ) = lora_tab(headless=headless)
                # with gr.Tab('Utilities'):
                #     utilities_tab(
                #         train_data_dir_input=train_data_dir_input,
                #         reg_data_dir_input=reg_data_dir_input,
                #         output_dir_input=output_dir_input,
                #         logging_dir_input=logging_dir_input,
                #         enable_copy_info_button=True,
                #         headless=headless,
                #     )

            # Show the interface
            launch_kwargs = {}
            username = kwargs.get('username')
            password = kwargs.get('password')
            server_port = kwargs.get('server_port', 0)
            inbrowser = kwargs.get('inbrowser', False)
            share = kwargs.get('share', False)
            server_name = kwargs.get('listen')

            launch_kwargs['server_name'] = server_name
            if username and password:
                launch_kwargs['auth'] = (username, password)
            if server_port > 0:
                launch_kwargs['server_port'] = server_port
            if inbrowser:
                launch_kwargs['inbrowser'] = inbrowser
            if share:
                launch_kwargs['share'] = share
            log.info(launch_kwargs)
            interface.launch(**launch_kwargs)
    except KeyboardInterrupt:
        # Code to execute when Ctrl+C is pressed
        print("You pressed Ctrl+C!")
    

if __name__ == '__main__':
    # torch.cuda.set_per_process_memory_fraction(0.48)
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--listen',
        type=str,
        default='127.0.0.1',
        help='IP to listen on for connections to Gradio',
    )
    parser.add_argument(
        '--username', type=str, default='', help='Username for authentication'
    )
    parser.add_argument(
        '--password', type=str, default='', help='Password for authentication'
    )
    parser.add_argument(
        '--server_port',
        type=int,
        default=0,
        help='Port to run the server listener on',
    )
    parser.add_argument(
        '--inbrowser', action='store_true', help='Open in browser'
    )
    parser.add_argument(
        '--share', action='store_true', help='Share the gradio UI'
    )
    parser.add_argument(
        '--headless', action='store_true', help='Is the server headless'
    )

    args = parser.parse_args()

    UI(
        username=args.username,
        password=args.password,
        inbrowser=args.inbrowser,
        server_port=args.server_port,
        share=args.share,
        listen=args.listen,
        headless=args.headless,
    )