import { SlashCommandBuilder } from "discord.js";
import db from "../../db.js"

export const data = new SlashCommandBuilder()
    .setName('schedule')
    .setDescription('Initiates scheduling with user argument')
    .addUserOption(o => o.setName('user').setDescription('the user to schedule with').setRequired(true))

export async function execute(interaction)
{
    const user = interaction.options.getUser('user')

    try
    {
        user.send(
            `Hi,\n` +
            `I'm the GM bot for the Delco Dog Dads.\n` +
            `I handle scheduling and we're scheduled to play week w.\n` +
            `You may suggest a time or I can give you some options.`
        )
        await db.setConversationState(user.id, `initiated`)
        interaction.reply("scheduling dm sent")
    }
    catch (error)
    {
        interaction.reply(`scheduling dm couldn't sent to ${user.username}\n${error}`)
    }
}