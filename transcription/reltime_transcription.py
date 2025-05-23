import asyncio
import base64
import json
import os
from pathlib import Path

import pyaudio
import streamlit as st
import websockets

if 'text' not in st.session_state:
    st.session_state['text'] = 'Listening...'
    st.session_state['run'] = False

st.sidebar.header('Audio Parameters')

base_dir = os.path.dirname(os.path.abspath(__file__))

FRAMES_PER_BUFFER = int(st.sidebar.text_input('Frames per buffer', 3200))
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = int(st.sidebar.text_input('Rate', 16000))
p = pyaudio.PyAudio()

stream = p.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    input=True,
    frames_per_buffer=FRAMES_PER_BUFFER
)

st.title('🎙️ Real-Time Transcription App')

with st.expander('About this App'):
    st.markdown('''
	This Streamlit app uses the AssemblyAI API to perform real-time transcription.

	Libraries used:
	- `streamlit` - web framework
	- `pyaudio` - a Python library providing bindings to [PortAudio](http://www.portaudio.com/) (cross-platform audio processing library)
	- `websockets` - allows interaction with the API
	- `asyncio` - allows concurrent input/output processing
	- `base64` - encode/decode audio data
	- `json` - allows reading of AssemblyAI audio output in JSON format
	''')

col1, col2 = st.columns(2)


def download_transcription():
    read_txt = open(os.path.join(base_dir, 'transcription.txt'), 'r')
    st.download_button(
        label="Download transcription",
        data=read_txt,
        file_name="transcription_output.txt",
        mime="text/plain"
    )

def start_listening():
    st.session_state['run'] = True

def stop_listening():
    st.session_state['run'] = False

col1.button('Start', on_click=start_listening)
col2.button('Stop', on_click=stop_listening)

async def send_receive():
    URL = f"wss://api.assemblyai.com/v2/realtime/ws?sample_rate={RATE}"
    print(f'Connecting websocket to url ${URL}')

    async with websockets.connect(
        URL,
        extra_headers=(("Authorization", st.secrets['api_key']),),
        ping_interval=5,
        ping_tieout=20
    ) as _ws:
        await asyncio.sleep(0.1)
        print("Receiving messages ...")

        session_begins = await _ws.recv()
        print(session_begins)
        print("Sending messages ...")

        async def send():
            while st.session_state['run']:
                try:
                    data = stream.read(FRAMES_PER_BUFFER)
                    data = base64.b64encode(data).decode("utf-8")
                    json_data = json.dumps({"auto_data":str(data)})
                    await _ws.send(json_data)

                except websockets.exceptions.ConnectionClosedError as e:
                    print(e)
                    assert e.code == 4008
                    break
                except Exception as e:
                    print(e)
                    assert False, "Not a websocket 4008 error"

                await asyncio.sleep(0.01)

        async def receive():
            while st.session_state['run']:
                try:
                    result_str = await _ws.recv()
                    result = json.loads(result_str)['text']
                    print(result)
                    if json.loads(result_str)['message_type'] == 'FinalTranscript':
                        st.session_state['text'] = result
                        st.write(st.session_state['text'])

                        transcription_txt = open('transcription.txt', 'a')
                        transcription_txt.write(st.session_state['text'])
                        transcription_txt.write(' ')
                        transcription_txt.close()

                except websockets.exceptions.ConnectionClosedError as e:
                    print(e)
                    assert e.code == 4008
                    break
                except Exception as e:
                    print(e)
                    assert False, "Not a websocket 4008 error"

        send_result, recv_result = await asyncio.gather(send(), receive())

asyncio.run(send_receive())

if Path(os.path.join(base_dir, 'transcription.txt')).is_file():
    st.markdown('### Download ###')
    download_transcription()
    os.remove(os.path.join(base_dir, 'transcription.txt'))