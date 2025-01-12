from openai import OpenAI

def generate_image(prompt):
    client = OpenAI()
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        quality="standard",
        n=1,
    )
    return response.data[0].url

if __name__ == "__main__":
    input = input("What to generate? ")
    url = generate_image(input)
    print(url)

