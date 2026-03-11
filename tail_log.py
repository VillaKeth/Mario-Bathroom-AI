with open('server_startup.log', 'r') as f:
    lines = f.readlines()
    for line in lines[-40:]:
        print(line, end='')
