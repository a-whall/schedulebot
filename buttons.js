import { ActionRowBuilder, ButtonBuilder, ButtonStyle } from "discord.js"



// Returns a new set of components but with the button customId matching `name` set to primary style.
// Assumes the original button components were another style so Primary indicates a user selection.
// Also disables all button components since it's assumed a selection is final.
function selected(name, rows)
{
    return rows.map(row =>
    {
        new ActionRowBuilder().addComponents(row.components.map(button =>
            {
                const newButton = ButtonBuilder.from(button)
                    .setDisabled(true)
                if (button.customId.includes(name))
                {
                    newButton.setStyle(ButtonStyle.Primary)
                }
                return newButton
            }
        ))
    })
}



function confirmation(confirm_disabled, cancel_disabled)
{
    const confirm_button = new ButtonBuilder()
        .setCustomId('confirm')
        .setLabel('Confirm')
        .setStyle(ButtonStyle.Success)
        .setDisabled(confirm_disabled)

    const cancel_button = new ButtonBuilder()
        .setCustomId('cancel')
        .setLabel('Cancel')
        .setStyle(ButtonStyle.Danger)
        .setDisabled(cancel_disabled)

    const row = new ActionRowBuilder().addComponents(confirm_button, cancel_button)

    return [row]
}



function time_selection(...suggested_times)
{
    const rows = []
    let row = new ActionRowBuilder()
    suggested_times.forEach((time_suggestion, i) =>
    {
        if (i > 0 && i % 5 === 0)
        {
            rows.push(row)
            row = new ActionRowBuilder()
        }
        row.addComponents(
            new ButtonBuilder()
                .setCustomId(`time_${time_suggestion}`)
                .setLabel(time_suggestion)
                .setStyle(ButtonStyle.Secondary)
        )
    })
    rows.push(row)
    return rows
}



const buttons = {
    confirmation,
    selected,
    time_selection
}



export default buttons