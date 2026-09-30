-- ChatTags: shows a colored tag like [VIP] in front of chat messages (milestone 3).
-- Put this LocalScript in StarterPlayer > StarterPlayerScripts.
-- The server decides who gets a tag (ShopServer sets the ChatTag attribute); this only draws it.

local Players = game:GetService("Players")
local TextChatService = game:GetService("TextChatService")

TextChatService.OnIncomingMessage = function(message)
	local properties = Instance.new("TextChatMessageProperties")
	local source = message.TextSource
	local speaker = source and Players:GetPlayerByUserId(source.UserId)
	local tag = speaker and speaker:GetAttribute("ChatTag")
	if tag then
		local color = speaker:GetAttribute("ChatTagColor") or "#FFFFFF"
		properties.PrefixText = string.format('<font color="%s">[%s]</font> %s', color, tag, message.PrefixText)
	end
	return properties
end
