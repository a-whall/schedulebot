import pg from "pg"

const pool = new pg.Pool(
{
    user: 'postgres',
    host: 'localhost',
    database: 'DiscordScheduleBot',
    password: process.env.PG_PASSWORD,
    port: 5432
})

async function getConversationState(user_id)
{
    const res = await pool.query('SELECT * FROM conversations WHERE user_id = $1', [user_id])
    return res.rows[0]
}

async function setConversationState(user_id, state)
{
    await pool.query('INSERT INTO conversations (user_id, state) VALUES ($1, $2) ON CONFLICT (user_id) DO UPDATE SET state = $2', [user_id, state])
}

const db = {
    getConversationState,
    setConversationState
}

export default db