import time
from flask import Flask, request, jsonify
import pyttsx3
import threading
import socket
import queue
import json
import ollama
import difflib
import pygame
import threading
import speech_recognition as sr
import requests
import json
from faster_whisper import WhisperModel
import tempfile
import scipy.io.wavfile

# === Initialize Pygame ===
pygame.init()
pygame.joystick.init()

app = Flask(__name__)
tts_queue = queue.Queue()

# === Text-to-Speech ===
engine = pyttsx3.init(driverName='sapi5')
voices = engine.getProperty('voices')
engine.setProperty('voice', voices[0].id)

# === Load DCS-BIOS Labels ===
with open("F-15E.json", "r") as f:
    F15_TELEMETRY_DICTIONARY = json.load(f)

label_desc = {}
for section in F15_TELEMETRY_DICTIONARY:
    for entry, data in F15_TELEMETRY_DICTIONARY[section].items():
        label_desc[entry] = data.get("description", "")

VALUE_MAPS = {
    "MASTER_ARM_SW": {
        "SAFE": 0, "OFF": 0,
        "ARM": 1, "ON": 1,
    },
    "R_TGP_LASER": {
        "OFF": 0,
        "STBY": 1,
        "ON": 2
    },
    # Add more label-specific maps here
}


# === System Prompt ===
system_prompt = """
    Assistant is a expert fighter jet AI co-pilot JSON builder designed to assist with a wide range of tasks.
    Your role is to analyze real-time aircraft telemetry and provide short, tactical voice responses to help the pilot. 
    Assistant is able to respond to the User and use tools using JSON strings that contain "action" which contains "aircraft", "description", "label", "value" or "messsage" which contains "value", "value" parameters.
    Assistant can also use tools by responding to the user with tool use instructions in the same "action" which contains "aircraft", "description", "label", "value" or "messsage" which contains "value" JSON format. Tools available to Assistant are:
    - You can send commands to the aircraft using DCS-BIOS API.
    - You can send messages to the Human Pilot.
    - You can execute commands to the aircraft using the tools.
    - "SendCommand": Sends a command to the aircraft via DCS-DTC API.
    - To use the SendCommand tool, Assistant should write like so:
        
json
        {
        "command": {
            "aircraft": "F-15E",
            "description": "turn on master arm switch",
            "label": "MASTER_ARM_SW",
            "value"": 1
            }
        }

    - "GetLabelByDescription": Sends a messsage to the Human Pilot.
    - To use the SendMessage tool, Assistant should write like so:
        
json
        {
        "messsage": {
            "value"": "Hello  Pilot, I am your AI co-pilot. How can I assist you today?"
            }
        }

        
    Here are some previous conversations between the Assistant and User:

    User: Hey how are you today?
    Assistant: 
json{"command":{}, "messsage": {"value"": "Hello  Pilot, I'm good. How can I assist you today?"}}

    User: The master arm is off, turn it on!
    Assistant: 
json{"command": {"aircraft": "F-15E","description": "turn on master arm switch",label": "MASTER_ARM_SW","value"": 1}, "message":"Aye sir! The master arm is now on."}

    User: Thanks, can you turn on the laser?
    Assistant: 
json{"command": {"aircraft": "F-15E","description": "turn on TGP laser arm switch","label": "R_TGP_LASER","value"": "set_state 1"}, "message":"Aye sir! The laser is now on."}

    User: Can you disable the master arm?
    Assistant: 
json{"command": {"aircraft": "F-15E","description": "turn off master arm switch","label": "MASTER_ARM_SW","value"": 0}, "message":"Aye sir! The master arm is now off."}

    User: can you turn off the laser?
    Assistant: 
json{"command": {"aircraft": "F-15E","description": "turn off TGP laser arm switch","label": "R_TGP_LASER","value"": "set_state 0"}, "message":"Aye sir! The laser is now off."}

    
DO NOT:
    - Ask the user for clarification.
    - Suggest writing code or how to analyze data.
    - Act like a chatbot or assistant.
    - Repeat the raw input or explain your reasoning.
    - Ask for more data or context.
    - Ask for clarification or additional information.
    - Do not repeat the raw input or explain your reasoning.
    
Values:
ARM = 1
SAFE = 0
ON = 1
OFF = 0

List of Labels and their descriptions (use them as reference when responding to the user, and use the labels exactly as they are written here. Format LABEL_NAME: DESCRIPTION, refer to the labels by their names only, do not use the descriptions in your responses): 
""" +  "\n".join(
    f"{label}: {desc} ({', '.join([f'{k}={v}' for k, v in VALUE_MAPS[label].items()])})"
    if label in VALUE_MAPS else f"{label}: {desc}"
    for label, desc in label_desc.items()
)

sys_message = {"role": "system", "content": system_prompt}
message_list = [sys_message]

# === Tool Function Logic ===
def send_dcs_bios_command(label: str, value):
    # Normalize textual values
    if isinstance(value, str):
        v = value.lower()
        if label in VALUE_MAPS:
            value = VALUE_MAPS[label].get(v, v)
        elif v in ["safe", "off", "disabled"]:
            value = 0
        elif v in ["arm", "on", "enabled"]:
            value = 1
        else:
            try:
                value = int(value)
            except ValueError:
                print(f"❌ Invalid value for {label}: {value}")
                return

    try:
        message = f"{label} {value}\n"
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(message.encode('utf-8'), ("127.0.0.1", 7778))
        print(f"📤 Sent to DCS-BIOS: {message.strip()}")
    except Exception as e:
        print(f"❌ Error sending to DCS-BIOS: {e}")



def get_label_by_description(description: str) -> str:
    description = description.lower().strip()

    # 1. Exact match first
    for label, desc in label_desc.items():
        if description == desc.lower().strip() or description == label.lower().strip():
            print(f"✅ Exact match: {label} for '{description}'")
            return label

    # 2. Substring / partial phrase match
    for label, desc in label_desc.items():
        desc_l = desc.lower()
        if description in desc_l and "light" not in desc_l and "indicator" not in desc_l:
            print(f"🔍 Substring match: {label} in '{desc}'")
            return label

    # 3. Token match fallback
    for label, desc in label_desc.items():
        for token in description.split():
            if token in desc.lower() or token in label.lower():
                print(f"🧪 Token match: {token} -> {label}")
                return label

    # 4. Use similarity (Levenshtein close match) as fallback
    all_descs = list(label_desc.values())
    closest = difflib.get_close_matches(description, all_descs, n=1, cutoff=0.7)
    if closest:
        for label, desc in label_desc.items():
            if desc == closest[0]:
                print(f"🤖 Similarity match: '{description}' ≈ '{desc}' → {label}")
                return label

    print(f"❌ No good match found for '{description}'")
    return None


tools = [
    {
        'type': 'function',
        'function': {
            'name': 'send_dcs_bios_command',
            'description': 'Send command to DCS-BIOS using label and value',
            'parameters': {
                'type': 'object',
                'properties': {
                    'label': {'type': 'string'},
                    'value': {'type': 'string'},
                },
                'required': ['label', 'value']
            }
        }
    },
    {
        'type': 'function',
        'function': {
            'name': 'get_label_by_description',
            'description': 'Get DCS-BIOS label by description to use in commands',
            'parameters': {
                'type': 'object',
                'properties': {
                    'label': {'type': 'string'},
                    'value': {'type': 'string'},
                },
                'required': ['label', 'value']
            }
        }
    }
]

# === TTS Worker ===
def tts_worker():
    while  not stop_event.is_set():
        msg = tts_queue.get()
        if msg:
            try:
                engine.say(msg)
                engine.runAndWait()
            except Exception as e:
                print(f"❌ TTS error: {e}")

# === Flask Telemetry Endpoint ===
@app.route("/telemetry", methods=["POST"])
def telemetry():
    data = request.json
    if not data or "telemetry" not in data:
        return jsonify({"error": "No telemetry provided"}), 400

    joined = "\n".join(data["telemetry"])
    prompt = f"""
    Aircraft: F-15E
    Copilot: Analyze the following real-time telemetry and report status, warnings, or suggested actions.
    {joined}
    """

    reply = ollama.chat(
        model="llama3.1:8b",
        messages=[sys_message, {"role": "user", "content": prompt}],
        options={"temperature": 0.3}
    )

    if reply.message and "specific question" not in reply.message["content"]:
        tts_queue.put(reply.message["content"])

    return jsonify({"status": "ok", "reply": reply.message["content"]})


@app.route("/voice_command", methods=["POST"])
def voice_command():
    data = request.json
    print(f"Received voice command: {data}")
    
def stop_all():
    stop_event.set()
    
    for t in threading_list:
        t.join()
    print("All thread stopped, exiting...")
# === Debugging Tool Loop ===
def get_assistant_response(transcribed_text=None):
    user_input = ""
    if transcribed_text:
        user_input = transcribed_text
    else:
        user_input = input("🎤 Request: ")

    user_msg = {"role": "user", "content": f"Execute: Jarvis, {user_input}"}
    # message_list.clear()
    message_list.append(sys_message)
    message_list.append(user_msg)

    response = ollama.chat(
        model="llama3.1:8b",
        messages=message_list,
        tools=tools,
        options={"temperature": 0.4}
    )
    
    response.message.tool_calls.count
    print(f"\n🤖🔧Tool Assistant Response: {response.message.content}")
    if response.message.tool_calls:
        if len(response.message.tool_calls) > 0:
            print("🔧 Tool calls detected:")
            for tool_call in response.message.tool_calls:
                name = tool_call.function.name
                args = tool_call.function.arguments
                print(f"🔧 Tool: {name}, Args: {args}")

                if name == "send_dcs_bios_command":
                    label = get_label_by_description(args.get("label"))
                    print(f"📡 Sending command to DCS-BIOS: {label} with value {args['value']}")
                    send_dcs_bios_command(label=label, value=args['value'])
                    # Now send follow-up confirming execution
                    # message_list.append({
                    #     "role": "tool",
                    #     "tool_call_id": response.message.tool_calls.index(tool_call),
                    #     "name": name,
                    #     "content": "Command sent successfully to DCS-BIOS socket."
                    # })
                    user_msg = {"role": "Tool", "content": f"Response: Command sent to DCS-BIOS for {args['label']} with value {args['value']}"}
                    follow_up = ollama.chat(
                        model="llama3.1:8b",
                        messages=message_list,
                        options={"temperature": 0.4}
                    )
                    msg = follow_up.message.content
                    print("✅", msg)
                    tts_queue.put(msg)

                elif name == "get_label_by_description":
                    label = get_label_by_description(**args)
                    print(f"🎯 Resolved label: {label}")
                    tts_queue.put(f"The label for {args['description']} is {label}")
        else:
            print(f"🧠 Response: {response.message.content}")
            tts_queue.put(response.message.content)


CUSTOM_TERMS = {
    "teapot": "R_TGP_PW set to 2",
    "deep odd": "R_TGP_PW set to 2",
    "master arm": "MASTER_ARM",
    "mass term": "MASTER_ARM",
    "GPU 12": "GBU-12",
    "gbu twelve": "GBU-12",
    "boy": "R_TGP_PW set to 2",
    "Deep Body": "R_TGP_PW set to 2",
    "deep body": "R_TGP_PW set to 2",
    "G-B-U-12": "GBU-12",
    "Master Army": "MASTER_ARM",
    "targeted power of the": "R_TGP_PW set to 2",
    "lasers": "R_TGP_LASER",
    "laser": "R_TGP_LASER",
}

def correct_transcript(text):
    for wrong, correct in CUSTOM_TERMS.items():
        text = text.lower().replace(wrong.lower(), correct)
    return text

stop_event = threading.Event()

# === Function 1: Show all button presses ===

model = WhisperModel("base", compute_type="int8", device="cpu")

def listen_all_gamepad_buttons():
    print("🎮 Listening for all gamepad button presses...")
    while not stop_event.is_set():
        pygame.event.pump()
        for i in range(pygame.joystick.get_count()):
            joystick = pygame.joystick.Joystick(i)
            joystick.init()
            for j in range(joystick.get_numbuttons()):
                if joystick.get_button(j):
                    print(f"🕹️ Joystick {i} - Button {j} pressed")
                    continue
        pygame.time.wait(100)


def transcribe_audio_faster_whisper(audio_bytes):
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmpfile:
        # Save byte data to WAV file
        tmpfile.write(audio_bytes)
        tmpfile.flush()
        tmp_path = tmpfile.name

    segments, _ = model.transcribe(tmp_path, language="en")
    return " ".join([seg.text.strip() for seg in segments])

# === Function 2: Trigger STT via specific button ===
def listen_for_trigger_and_start_stt(trigger_joystick_index=1, trigger_button_index=4):
    print(f"🎤 Waiting for trigger: Joystick {trigger_joystick_index}, Button {trigger_button_index}")
    while not stop_event.is_set():
        pygame.event.pump()
        if pygame.joystick.get_count() > trigger_joystick_index:
            throttle = pygame.joystick.Joystick(trigger_joystick_index)
            throttle.init()
            if throttle.get_button(35):
                print("Finishing STT session...")
                pygame.quit()
                stop_all()
            if throttle.get_button(trigger_button_index):
                print("🎙️ Trigger button pressed! Starting STT...")
                start_speech_to_text()
                pygame.time.wait(1000)  # Prevent multiple triggers

        pygame.time.wait(100)

# def stop_all_threads():
#     for thread in threading_list:
#         thread

# === Function 3: Speech-to-Text and send to Flask ===
def start_speech_to_text():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("🗣️ Listening for voice input...")
        try:
            audio = recognizer.listen(source, timeout=5)
            wav_data = audio.get_wav_data()
            text = transcribe_audio_faster_whisper(wav_data)
            print(f"📝 Transcribed text: {text}")
            text = correct_transcript(text)
            print(f"✅ Corrected text: {text}")
            get_assistant_response(transcribed_text=text)
        except sr.WaitTimeoutError:
            print("⏱️ Timeout: No speech detected.")
        except sr.UnknownValueError:
            print("❌ Could not understand the speech.")
        except sr.RequestError as e:
            print(f"❌ STT error: {e}")

def main():
    while  not stop_event.is_set():
        get_assistant_response()


threading_list = [threading.Thread()]


# === Main Launch ===
if __name__ == "__main__":
    threading_list.clear()
    
    tts_t = threading.Thread(target=tts_worker)
    main_t = threading.Thread(target=main)
    listener_t = threading.Thread(target=listen_for_trigger_and_start_stt)
    # gamepad_t =  threading.Thread(target=listen_all_gamepad_buttons)
    
    threading_list.append([tts_t, main_t, listener_t])
    
    time.sleep(2)
    
    
    main_t.start()
    tts_t.start()
    listener_t.start()
    # gamepad_t.start()
    
    
    print("🚀 AI Copilot ready for input...")

    # Manual test loop
    # while True:
    #     time.sleep(0.2)

