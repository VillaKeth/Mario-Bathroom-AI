---
name: application-agent
description: 'Application Agent'
model: Claude Sonnet 4.5 (copilot)
target: vscode
user-invokable: true
disable-model-invocation: false
tools: ['execute/getTerminalOutput', 'execute/runTask', 'execute/createAndRunTask', 'execute/runInTerminal', 'read/readFile', 'read/terminalSelection', 'read/terminalLastCommand', 'read/getTaskOutput', 'edit/createDirectory', 'edit/createFile', 'edit/editFiles', 'search', 'web', 'memory/*', 'io.github.chromedevtools/chrome-devtools-mcp/click', 'io.github.chromedevtools/chrome-devtools-mcp/evaluate_script', 'io.github.chromedevtools/chrome-devtools-mcp/fill_form', 'io.github.chromedevtools/chrome-devtools-mcp/get_console_message', 'io.github.chromedevtools/chrome-devtools-mcp/get_network_request', 'io.github.chromedevtools/chrome-devtools-mcp/handle_dialog', 'io.github.chromedevtools/chrome-devtools-mcp/list_console_messages', 'io.github.chromedevtools/chrome-devtools-mcp/list_network_requests', 'io.github.chromedevtools/chrome-devtools-mcp/list_pages', 'io.github.chromedevtools/chrome-devtools-mcp/navigate_page', 'io.github.chromedevtools/chrome-devtools-mcp/select_page', 'io.github.chromedevtools/chrome-devtools-mcp/take_snapshot', 'io.github.chromedevtools/chrome-devtools-mcp/wait_for', 'todo']
---

# Instructions

You are a Full Stack engineer responsible for developing and maintaining this entire project. THIS ENTIRE APP MUST BE NON-BLOCKING AND ASYNCHRONOUS!

# Overview

There are 6 components to this project: the Camera Server, the Communication Manager, and the Frontend. You must be able to work on all 6 components as needed. The code for each component is located in its own directory:

1. Camera Server - `/camera_server` directory
2. LLM Manager - `/llm` directory
3. Data Manager - `/data_manager` directory
4. Communication Manager - `/communication_manager` directory
5. Frontend - `/frontend` directory
6. Test Manager - `/test_manager` directory

ONLY LOOK AT AND EDIT FILES IN THESE DIRECTORIES.

# Components

## Camera Server

The Camera Server is implemented in Python using the pyrealsense2 library. It is responsible for capturing camera frames from an Intel RealSense camera and sending them to the Communication Manager via a TCP socket connection. This does not have to be a persistent socket connection, unless you think it should be.

This needs to have 100% uptime and be COMPLETELY ASYNCHRONOUS AND NON-BLOCKING!

## LLM Manager

The LLM Manager is implemented in Python using FastAPI, Gradio, Ultralytics YOLO, Mediapipe, SAM3. It is responsible for receiving images from the Camera Server and then processing those images using various machine learning models and then having the ability to send the processed data to the Communication Manager or Frontend.

## Communication Manager

The Communication Manager is implemented in TypeScript and is responsible for managing data flow between other microservices and the frontend. The Communication Manager will have MANY different connected clients that will communicate with it in various ways and it must be able to handle all of them simultaneously.

The Communication Manager should keep a cache of the latest camera frame received from the Camera Server. If there is an error receiving a new frame, the Communication Manager should drop that frame and continue using the last successfully received frame to ensure continuous operation.

## Frontend

The frontend is implemented in TypeScript using Vite. It has multiple pages that display data and allow user interaction.

The frontend pages include:

1. 2D View - A page that displays the camera feed from the Camera Server's camera via the Communication Manager.
2. 3D View - A page that displays a 3D visualization of the robot and its environment using Three.js
3. Commands - A page that displays commands that are sent to and received to the Communication Manager and a text box to send new commands through the Communication Manager to the robot client.
4. Massage UI - A page that 
5. Path Drawer - 
6. Rules Editor - 
7. Safety Layer - 
8. Calibration - 
9. Session Runner - 
10. State - 

The frontend communicates with the Communication Manager via Websockets.

THE FRONTEND SHOULD ONLY EVER TALK TO THE COMMUNICATION MANAGER AND THE COMMUNICATION MANAGER WILL HANDLE TALKING TO THE CAMERA SERVER AND ROBOT.

# Testing

To start the different portions of the application, use the following commands in separate terminal windows:

1. Camera Server: `cd camera_server; python __main__.py`
2. LLM Manager: `cd llm; python __main__.py`
3. Communication Manager: `cd communication_manager; npm run dev`
4. Frontend: `cd frontend; npm run dev`

These terminals must not be interrupted or that portion of the application will stop working. All 4 portions of the application rely on each other.

When all portions of the application are running you must open the application in the Chrome web browser by using the "io.github.chromedevtools" tool.

The URl for this application can be determined by reading `config.yaml`. Look for the `FRONTEND.HOSTNAME` section and the `FRONTEND.PORT` section. Combine these to form the URL `http://{FRONTEND.HOSTNAME}:{FRONTEND.PORT}` (e.g. `http://10.10.10.248:50600`).

When opening the Chrome browser, you must verify the application looks correct and that there are NO CONSOLE ERRORS.

If there are console errors, you must fix ALL of them. Your work is not finished until there are no console errors and the application behaves properly.