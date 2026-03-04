---
name: camera-server-agent
description: 'Camera Server Agent'
target: vscode
user-invokable: true
disable-model-invocation: false
argument-hint: Agent for creating and maintaining the Camera Server microservice.
tools: ['execute/getTerminalOutput', 'execute/runTask', 'execute/createAndRunTask', 'execute/runInTerminal', 'read/readFile', 'read/terminalSelection', 'read/terminalLastCommand', 'read/getTaskOutput', 'edit/createDirectory', 'edit/createFile', 'edit/editFiles', 'search', 'web', 'memory/*', 'io.github.chromedevtools/chrome-devtools-mcp/click', 'io.github.chromedevtools/chrome-devtools-mcp/evaluate_script', 'io.github.chromedevtools/chrome-devtools-mcp/fill_form', 'io.github.chromedevtools/chrome-devtools-mcp/get_console_message', 'io.github.chromedevtools/chrome-devtools-mcp/get_network_request', 'io.github.chromedevtools/chrome-devtools-mcp/handle_dialog', 'io.github.chromedevtools/chrome-devtools-mcp/list_console_messages', 'io.github.chromedevtools/chrome-devtools-mcp/list_network_requests', 'io.github.chromedevtools/chrome-devtools-mcp/list_pages', 'io.github.chromedevtools/chrome-devtools-mcp/navigate_page', 'io.github.chromedevtools/chrome-devtools-mcp/select_page', 'io.github.chromedevtools/chrome-devtools-mcp/take_snapshot', 'io.github.chromedevtools/chrome-devtools-mcp/wait_for', 'todo']
---

# Instructions

Only look at code related to the Camera Server. This code is located in the `/camera_server` directory. You MUST ONLY edit files in the `/camera_server` directory.

If you need to check the version of any installed packages just look inside of the `requirements.txt` file located in the `/camera_server` directory.

# Overview

The Camera Server is implemented in Python and is responsible for capturing images from an Intel RealSense camera.

DO NOT create a simulated camera server. The Camera Server MUST interface with a real Intel RealSense camera connected to the machine via USB. If there is a failure to connect to the camera, the application MUST throw an error and stop execution.

The Camera Server will provide 3 methods of access for clients to request camera data from the Camera Server:

1. A persistent TCP socket connection
2. A WebRTC connection
3. A websocket interface

There should also be a Gradio-based frontend that displays the camera stream.

# Configuration

The Camera Server should always use values from the `config.yaml` file located in the root `/` directory. Never hardcode any URLs, hostnames, or port numbers. If these values cannot be read from the `config.yaml` file, you MUST throw an error and stop execution.

The following configuration parameters apply to the Camera Server application:

1. `CAMERA_SERVER.GRADIO.HOSTNAME`: The hostname or IP address where the Camera Server's Gradio interface will run.
2. `CAMERA_SERVER.GRADIO.PORT`: The port number on which the Camera Server's Gradio interface will run.
3. `CAMERA_SERVER.HEIGHT`: The height resolution for the Intel Realsense camera stream.
4. `CAMERA_SERVER.FRAMES_PER_SECOND`: The frames per second (FPS) rate for the Intel Realsense camera stream.
5. `CAMERA_SERVER.SOCKET.HOSTNAME`: The hostname or IP address for the camera socket connection.
6. `CAMERA_SERVER.SOCKET.PORT`: The port number for the camera socket connection.
7. `CAMERA_SERVER.WEB_RTC.HOSTNAME`: The hostname or IP address for the WebRTC connection.
8. `CAMERA_SERVER.WEB_RTC.PORT`: The port number for the WebRTC connection.
9. `CAMERA_SERVER.WEBSOCKET.HOSTNAME`: The hostname or IP address for the WebSocket connection.
10. `CAMERA_SERVER.WEBSOCKET.PORT`: The port number for the WebSocket connection.
11. `CAMERA_SERVER.WIDTH`: The width resolution for the Intel Realsense camera stream.

You should load the configuration from `config.yaml` one time at the start of the application. Those values should be stored in a global variable, or singleton class for easy access throughout the application and to avoid unnecessary repeated file reads.

# Backend

The Camera Server backend should have a standard TCP socket server, a WebRTC server, and a websocket server. Each of these servers will stream raw camera frames from the Intel RealSense camera in a non-blocking asynchronous manner.

All three of these servers MUST be COMPLETELY INDEPENDENT of each other, so that clients can connect to any of the three servers without affecting the others.

All three servers MUST be able to run simultaneously and each of them MUST be able to handle multiple clients connecting at the same time.

# Frontend

The frontend for the Camera Server should use Gradio to display a live feed of the camera stream. Use a generator function to retrieve frames instead of some arbitrary refresh interval to ensure the video stream is as smooth as possible.

There should be a button in the Gradio interface that allows users to open the camera stream in an OpenCV window. This should be the ONLY button in the Gradio interface.

Both the Gradio interface and the OpenCV window should have their own FPS calculations that are displayed in their respective views.

# Testing

To start the application, navigate to the `/camera_server` directory and run the command `python __main__.py` in a terminal. This terminal will be continuously running and cannot be interrupted. If you need to run other commands, you MUST open a new terminal.

After the application has started, you MUST verify that the Camera Server is functioning correctly. This is done by opening the Gradio interface in the Chrome web browser. To open the Chrome web browser, you MUST use the "**io.github.chromedevtools/chrome-devtools-mcp**" tool. If you need to take a screenshot to view the webpage properly you MUST use the "**playwright**" tool. DO NOT use any other method to open the Chrome web browser.

The URl for this application can be determined by reading `config.yaml`. Look for the `CAMERA_SERVER.GRADIO.HOSTNAME` section and the `CAMERA_SERVER.GRADIO.PORT` section. Combine these to form the URL `http://{CAMERA_SERVER.GRADIO.HOSTNAME}:{CAMERA_SERVER.GRADIO.PORT}` (e.g. `http://10.10.10.248:50500`).

When opening the Chrome browser, you must verify the application looks correct. The application is correct if the following conditions are met:

1. The video stream from the Camera Server is displaying correctly.
2. Any buttons that are present should be clickable and behave as intended.
3. ALL console errors are fixed.

Your work is NOT finished until there are NO console errors, and the video stream is displaying correctly on the webpage.

You MUST continue to iterate until there are no errors and the video stream is displaying correctly.