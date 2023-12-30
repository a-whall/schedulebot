"""
Purpose:
    Run this file to compute intent embeddings and save them to a .pt file.
    Edit the phrases dictionary to adjust intent detection.
"""
import torch
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")

phrases = {
    "greeting": [
        "Hi.",
        "What's up.",
        "Good day.",
        "Hello.",
        "Yo."
    ],
    "suggestion": [
        "How about next Monday at 3 PM?",
        "Can we meet on Friday morning?",
        "Is Wednesday at 10 o'clock good for you?",
        "Let's schedule it for Tuesday afternoon.",
        "I'm available this Thursday at 2 PM, does that work?"
    ],
    "availability_request": [
        "When are you free to meet?",
        "What times do you have open?",
        "Can you suggest a suitable time?",
        "Tell me your available slots.",
        "Do you have time this week?"
    ],
    "confirmation": [
        "Sounds good.",
        "Sure.",
        "Yeah.",
        "Yes.",
        "That time works for me.",
        "I'm okay with the proposed schedule.",
        "Yes, let's lock in that time.",
        "I agree with your time suggestion.",
        "That schedule is perfect for me."
    ],
    "rescheduling": [
        "Can we move it to a different day?",
        "I need to reschedule our meeting.",
        "That time doesn't work for me, how about another?",
        "Is it possible to change the meeting time?",
        "I have to push our meeting to a later time."
    ]
}

# Save a dictionary where each key is a category and each value is a tensor of size [N_c, H],
# where N_c is the number of sentences for that category and H is the size of the embedding vector (384).
torch.save(
    obj={
        category: model.encode(sentences, convert_to_tensor=True)
        for category, sentences in phrases.items()
    },
    f='intent_embeddings.pt'
)