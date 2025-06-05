# 🛫 DCS AI Copilot (For Now only Compatible is the F-15E Strike Eagle)

An AI-powered copilot system for **DCS World** that uses real-time telemetry data and natural language voice input to enhance your combat flight experience.

> ⚠️ **Early Version** – Current functionality is limited to:
> - Analyzing telemetry data to provide insights, warnings, and tips.
> - Controlling simple buttons and switches **one at a time** using AI-generated commands.
> - Interacting with The F-15E
---

## 📦 Features

✅ Real-time telemetry parsing  
✅ Voice feedback using TTS  
✅ Voice command input via joystick + microphone  
✅ AI integration via [Ollama](https://ollama.com) using LLaMA 3.1  
✅ Control DCS-BIOS-enabled switches and buttons with AI-generated commands

---

## 🛠️ Requirements

### 🔧 System Requirements

- **.NET SDK 10.0+**
- **Python 3.10.16**
- **DCS World** with:
  - [DCS-BIOS](https://github.com/DCS-Skunkworks/dcs-bios/tree/main) properly installed and configured
### 📦 Python Dependencies

Install via:

```bash
Doubl click on Install.bat
```
## Instalation and Configuration
- Install the requiments and check if they're working
- Run the Install.bat once to install required packages from Python
- Use notepad to edit dcs_copilot_main.py 
  - near the end of the file, you will find this part
```Python
    # gamepad_t =  threading.Thread(target=listen_all_gamepad_buttons)

    threading_list.append([tts_t, main_t, listener_t])

    time.sleep(2)


    main_t.start()
    tts_t.start()
    listener_t.start()
    # gamepad_t.start() 
```
- Change it to 
```Python
    gamepad_t =  threading.Thread(target=listen_all_gamepad_buttons)

    threading_list.append([tts_t, main_t, listener_t])

    time.sleep(2)


    main_t.start()
    #tts_t.start()
    #listener_t.start()
    gamepad_t.start() 
```
- Run the Run.bat with double click, it shoul display the current buttons for your controll, press the button that you want to use as the trigger for the AI listener, and see what it it's gamepad index number and button index.
- Edit the **listen_for_trigger_and_start_stt(trigger_joystick_index=1, trigger_button_index=4)** changint the joystick index and button index for the ones listed in the terminal
- Change the end back to 
```Python
    # gamepad_t =  threading.Thread(target=listen_all_gamepad_buttons)

    threading_list.append([tts_t, main_t, listener_t])

    time.sleep(2)


    main_t.start()
    tts_t.start()
    listener_t.start()
    # gamepad_t.start() 
## Running and Fixing
```
- Save and close the file and then double click the Run.bat, you should see two terminals open
 
## Troubleshooting
- Ensure you only run the **Run.bat** AFTER the game was opened, and the mission started
- Ensure every requirement have been installed
