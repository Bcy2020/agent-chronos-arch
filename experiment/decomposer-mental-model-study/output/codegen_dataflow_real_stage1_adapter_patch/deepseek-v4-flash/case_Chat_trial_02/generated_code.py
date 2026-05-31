def ProcessChatCommand(input: Any) -> Any:
    validated_command, message_data = ParseAndValidateCommand(input)
    if validated_command == 'send':
        send_result = SendMessage(message_data)
        output = FormatResponse(send_result, None)
    elif validated_command == 'history':
        history_result = GetHistory(message_data)
        output = FormatResponse(history_result, None)
    elif validated_command == 'create_channel':
        create_result = CreateChannel(message_data)
        output = FormatResponse(create_result, None)
    elif validated_command == 'join':
        join_result = JoinChannel(message_data)
        output = FormatResponse(join_result, None)
    else:
        output = FormatResponse(None, 'Invalid command')
    return output