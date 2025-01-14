import re
import httpx
import logging
from openai import OpenAI
import ollama
from ollama import chat
from ollama import ChatResponse
from pydantic import BaseModel
from typing import Any

logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARN)

class Tool(BaseModel):
    name: str
    description: str

    def run(self):
        pass


class PythonCalculator(Tool):
    """
    calcular:
    Executa um cáculo e retorna um número usando Python e garante que números flutuantes são usados quando necessários. O input para esta ação deve ser uma expressão python válida
    ex: calcular: 4 * 7 / 3
    ex: calcular aceita uma formula númerica
    """
    
    def __init__(self):
        super().__init__(
            name="calcular", 
            description="""
            Executa um cáculo e retorna um número usando Python e garante que números flutuantes são usados quando necessários.
            ex: calcular: 4 * 7 / 3
            ex: calcular aceita uma formula númerica
            """)


    def run(self, formula: str):
        return eval(formula)

    def __str__(self):
        return f"{self.name}\n{self.description}"

    def __call__(self, formula):
        return self.run(formula)

class WikipediaTool(Tool):
    """
    wikipedia:
    A wikipedia possui informações atuais sobre conhecimentos gerais. Retorna um sumário após pesquisar na Wikipedia.
    ex: wikipedia: Django
    """
    
    def __init__(self):
        super().__init__(
            name="wikipedia", 
            description="""
            A wikipedia possui informações atuais sobre conhecimentos gerais. Retorna um sumário após pesquisar na Wikipedia.
            ex: wikipedia: Django
            """)


    def run(self, q):
        logging.info(f"wikipedia:params:{q}")
        response = httpx.get("https://en.wikipedia.org/w/api.php", params={
            "action": "query",
            "list": "search",
            "srsearch": q,
            "format": "json"
        })
        return response.json()["query"]["search"][0]["snippet"]

    def __str__(self):
        return f"{self.name}\n{self.description}"

    def __call__(self, q):
        return self.run(q)

class ChatHistory:
    messages: list[dict] = []

    def __init__(self, system_prompt=""):
        self.messages.append({"role": "system", "content": system_prompt})

    def append(self, message: str):
        self.messages.append({"role": "user", "content": message})

    def response(self, message: str):
        self.messages.append({"role": "assistant", "content": message})

class Chatbot(BaseModel):
    system: str | None = None 
    messages: list[dict] = []

    def __call__(self, message):
        self.messages.append({"role": "user", "content": message})
        result = self.execute()
        self.messages.append({"role": "assistant", "content": result})
        return result


class ChatbotOllama(Chatbot):

    def __init__(self, system=None):
        super().__init__(system=system)
        if system:
            self.messages.append({"role": "system", "content": self.system})

    def execute(self, chat_history: ChatHistory):
        #response = ollama.chat(model= "gemma2:9b", messages=chat_history.messages)
        response = ollama.chat(model= "llama3.1", messages=chat_history.messages)
        completion = response['message']['content']
        return completion


class ChatbotOpenAI(Chatbot):
    openai: Any = None

    def __init__(self, system=None):
        super().__init__(system=system)
        if system:
            self.messages.append({"role": "system", "content": self.system})
        self.openai = OpenAI()

    def execute(self):
        completion = self.openai.chat.completions.create(model="gpt-4o-mini", messages=self.messages)
        return completion.choices[0].message.content


calculator = PythonCalculator()
wikipedia = WikipediaTool()

prompt=f"""
Quando uma pergunta for feita você vai:
Usar Pensamento: para descrever o que você acha que devem ser as ações a serem tomadas.
As ferramentas disponíveis para ações são as seguintes:

Ações disponíveis:
---
{str(calculator)}
{str(wikipedia)}

chat:
Responde questão com informações já conhecidas pelo modelo.
ex: chat: Qual a capital do Brasil?
---
Responda com o nome da Ação disponível que deve ser executada e então você PAUSA.
Observação será o resultado de executar uma Ação

Você será chamado novamente com a observação

Exemplo de uma sessão:
Pergunta: Qual a capital da França e da Alemanha? 
Pensamento: Eu devo pesquisar conte
Ação: wikipedia: França
Ação: wikipedia: Alemanha

""";

prompt2 = """
Tente extrair a resposta final da observação recebida.
Se você conseguir gerar a resposta final responder da seguinte forma:

Resposta Final: {observação}

Se não for a resposta final, você deve voltar para a fase de 'Pensamento'.
"""


p3="""No final do loop você exibe a resposta.

Exemplo de uma sessão:
Pergunta: Qual a capital da França e da Alemanha? 
Pensamento: Eu devo pesquisar conte
Ação: wikipedia: França
PAUSA

Você será chamado novamente com isto:
Observação: França é um país. Sua captial é Paris. 

Você então irá retornar:
Resposta: Paris 
"""

#print(prompt)

action_re = re.compile(r"^Ação: (\w+): (.*)")

def chat(question):
    #chat = ChatbotOpenAI(system="Você responde as questões da maneira mais suscinta possível, sem explicações")
    system="Você responde as questões da maneira mais suscinta possível, sem explicações"
    hst = ChatHistory(system)
    chat = ChatbotOllama(hst)
    return chat(question)


acoes = {
    "calcular": calculator,
    "wikipedia": wikipedia,
    "chat": chat,
}

class Agente(BaseModel):
    name: str
    description: str = ""
    max_turns: int

    def __init__(self, name, max_turns=5):
        super().__init__(name=name, max_turns=max_turns)

    def run(self, task):
        print(task)

def query(question, max_turns=5):
    i = 0
    #bot = ChatbotOpenAI(prompt)
    bot = ChatbotOllama(prompt)
    hst = ChatHistory(prompt)

    next_prompt = question
    print(f"Respondendo a questão: {question}")
    while i < max_turns:
        i += 1
        print("Iteration: ", i)
        hst.append(next_prompt)
        result = bot.execute(hst)
        hst.response(result)

        if "Resposta Final" in result:
            logging.info(result)
            return
        
        logging.info(f"Pensamento: {result}{'|fim_pensamento|'}")

        actions = [action_re.match(a) for a in result.split("\n") if action_re.match(a)]
        logging.info(f"actions: {actions} --> {result}")
        if actions:
            obs = ""
            for a in actions:
                action, input = a.groups()
                if action not in acoes:
                    logging.error(f"Ação não encontrada: {action} {input}")
                    raise Exception(f"Ação não encontrada: {action} {input}")
                logging.info(f"Ação: {action}:{input} - Running")
                one_obs= acoes[action](input)
                logging.info(f"Observação: {one_obs}")
                obs = f"{obs}\n{one_obs}"
            hst.append(f"Observação: {obs}\n\n{prompt2}")
            next_prompt = bot.execute(hst) 
            if "Resposta Final" in next_prompt:
                logging.info(next_prompt)
                return
            logging.warn(f"Next prompt: {next_prompt}")
        else:
            return result

def main():
    question = input("Ask a question: ")
    resp = query(question)

if __name__ == '__main__':
    main()

