import { spawn } from "child_process"

function pythonChildProcess(discord_message, args, py_command='py', py_script='model.py')
{
    return new Promise((resolve, reject) =>
    {
        const pythonProcess = spawn(py_command, [py_script, ...args.map(arg => `--${arg}=${discord_message[arg]}`)])

        let stdout = ''
        let stderr = ''

        pythonProcess.stdout.on('data', data => stdout += `${data}\n`)

        pythonProcess.stderr.on('data', data => stderr += `${data}\n`)

        pythonProcess.on('close', exit_code =>
        {
            try
            {
                return (exit_code === 0) ? resolve(JSON.parse(stdout.toString()))
                : reject(new Error(`Process exited with code ${exit_code}\n\n${stderr}`))
            }
            catch (error)
            {
                return reject(new Error(`${error}\n\n${stdout.toString()}`))
            }   
        })
    })
}

export { pythonChildProcess }