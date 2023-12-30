import { Client, Partials, Collection, GatewayIntentBits } from "discord.js"
import "dotenv/config"
import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"
import { pythonChildProcess } from "./process.js"
import db from "./db.js" 
import buttons from "./buttons.js"



// Create a new client instance
const client = new Client(
{
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.GuildMessageReactions,
        GatewayIntentBits.MessageContent,
        GatewayIntentBits.GuildMembers,
        GatewayIntentBits.DirectMessages,
        GatewayIntentBits.DirectMessageReactions
    ],
    partials: [
        Partials.Message,
        Partials.Channel,
        Partials.Reaction
    ]
})



// Load commands from file
client.commands = new Collection()

const foldersPath = path.join(path.dirname(fileURLToPath(import.meta.url)), 'commands')
const commandFolders = fs.readdirSync(foldersPath)

for (const folder of commandFolders)
{
    const commandsPath = path.join(foldersPath, folder)
    const commandFiles = fs.readdirSync(commandsPath).filter(file => file.endsWith('.js'))

    for (const file of commandFiles)
    {
        const filePath = path.join(commandsPath, file)
        const command = await import(`file:${filePath}`)

        if ('data' in command && 'execute' in command)
        {
            console.log(`Setting command ${command.data.name}`)
            client.commands.set(command.data.name, command)
        }
        else
        {
            console.log(`[WARNING] The command at ${filePath} is incomplete`)
        }
    }
}



client.once("ready", readyClient =>
{
    console.log(`${readyClient.user.username} logged in.`)
    
    if (readyClient.user.id !== process.env.CLIENT_ID)
    {
        console.log("[WARNING] env client id does not match.")
    }
})



client.on("messageCreate", async message =>
{
    // Ignore self and bots
    if (message.author.id === client.user.id || message.author.bot === true)
    {
        return;
    }
    // Direct Message
    if (message.guildId === null)
    {
        let conversation = await db.getConversationState(message.author.id)
        message.state = conversation.state

        console.log(
            `DirectMessage from ${message.author.globalName} (${message.author.id})\n` +
            `- Message Content: "${message.content}"\n` +
            `- Stored State: ${message.state}`
        )

        message.channel.sendTyping()
        let result = await pythonChildProcess(message, ['content', 'state'])
        message.channel.send(
            `# ${result.response}\n` +
            `- confidence: ${result.score}\n` +
            `- interpreted as: ${result.question}\n` +
            `- intent detection:\n` +
            `  - ${Object.entries(result.intent_scores).map(([category,score])=>`${category}: ${score.toFixed(2)}`).join('\n  - ')}\n` +
            `- intent: ${result.intent}`
        )
        if ('poll' in result)
        {
            const [day, time] = result.poll.split('/')
            if (time === "")
            {
                time = "10pm"
            }
            const channel = client.channels.cache.get(process.env.GENERAL_CHANNEL_ID)
            if (channel)
            {
                let pollMessage = await channel.send(`How about ${day} at ${time}`)
                pollMessage.react('👍')
                pollMessage.react('👎')
                // Add the poll to a db table of polls
            }
            else
            {
                console.log(`[Warning] channel doesn't exist, poll can't be made.`)
            }
        }
    }
    // Server Message
    else
    {
        console.log(
            `ChannelMessage posted by ${message.author.globalName} (${message.author.id}) in #${message.channel.name} (${message.channel.id})`
        )
        // Ignore unless mentioned
        if (message.mentions.has(client.user.id))
        {
            const channel = message.client.channels.cache.get(message.channelId)
            if (message.content.toLowerCase().includes("options"))
            {
                await message.reply({
                    content: `Select One`,
                    components: buttons.time_selection('Monday 9:30pm', 'Tuesday 9pm', ' Wednesday 10pm')
                })
            }
            else
            {
                await message.reply({
                    content: 'Confirm??',
                    components: buttons.confirmation(false, false)
                })
            }

            // Strip mention
            // const mention = new RegExp(`<@!?${client.user.id}>`, 'g')
            // message.content = message.content.replace(mention, '').trim()
            // console.log(
            //     `Mentioned in channel ${channel.name} by ${message.author.globalName}\n` +
            //     `- content: ${message.content}`
            // )
            // message.channel.sendTyping()
            // let result = await pythonChildProcess(message, ['content'])
            // message.channel.send(`# ${result.response.answer}\n- confidence: ${result.response.score.toFixed(2)}\n- interpreted as: ${result.question}`)
        }        
    }
})



client.on("messageReactionAdd", async (reaction, user) =>
{
    console.log(`${user.username} reacted with ${reaction.emoji.name}`)
    // Check if "Polling" state too
    if (reaction.message.id === "Poll Message ID")
    {
        console.log(`${user.username} reacted with ${reaction.emoji.name}`)

        // Check update reaction counts
    }
    // Handle reactions from dms if "Awaiting Confirmation" state
})



client.on("messageReactionRemove", async (reaction, user) =>
{
    console.log(`${user.username} removed their reaction ${reaction.emoji.name}`)
    // Check if "Polling" state too
    if (reaction.message.id === "Active Poll Message ID")
    {
        console.log(`${user.username} removed their reaction ${reaction.emoji.name}`)
    }
})



client.on("interactionCreate", async interaction =>
{
    if (!interaction.isButton())
    {
        return
    }

    if (interaction.customId.startsWith('confirm'))
    {
        const original_message = await interaction.message.fetch()
        const cancel = original_message.components[0].components.find(component => component.customId === 'cancel')
        await original_message.edit({ components: buttons.confirmation(true, cancel.disabled) })
        await interaction.reply(`Confirmed`)
    }
    else if (interaction.customId.startsWith('cancel'))
    {
        const original_message = await interaction.message.fetch()
        const confirm = original_message.components[0].components.find(component => component.customId === 'confirm')
        await original_message.edit({ components: buttons.confirmation(confirm.disabled, true) })
        await interaction.reply(`Canceled`)
    }
    else if (interaction.customId.startsWith('time_'))
    {
        const original_message = await interaction.message.fetch()
        original_message.edit({ components: buttons.selected(interaction.customId, original_message.components) })
        let suggested_time = interaction.customId.split('_')[1]
        await interaction.reply(`Selected ${suggested_time}`)
    }
})



client.on("interactionCreate", async interaction =>
{
    if (!interaction.isChatInputCommand())
    {
        return
    }

    const command = interaction.client.commands.get(interaction.commandName)

    if (!command)
    {
        console.error(`No command matching ${interaction.commandName} was found.`)
        return
    }

    try
    {
        await command.execute(interaction)
    }
    catch (error)
    {
        console.error(error)

        if (interaction.replied || interaction.deferred)
        {
            await interaction.followUp({ content: 'There was an error while executing this command!', ephemeral: true })
        }
        else
        {
            await interaction.reply({ content: 'There was an error while executing this command!', ephemeral: true })
        }
    }
})



// Log in to Discord with your client's token
client.login(process.env.DISCORD_TOKEN)