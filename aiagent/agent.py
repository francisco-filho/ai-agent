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
    Executa um cáculo e retorna um número usando Python e garante que números flutuantes são usados quando necessários.
    ex: calcular: 4 * 7 / 3
    """
    
    def __init__(self):
        super().__init__(
            name="calcular", 
            description="""
            Executa um cáculo e retorna um número usando Python e garante que números flutuantes são usados quando necessários.
            ex: calcular: 4 * 7 / 3
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
        response = httpx.get("https://pt.wikipedia.org/w/api.php", params={
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

    def execute(self):
        response = ollama.chat(model= "llama3", messages=self.messages)
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
Você fala português e funciona em um loop de Pensamento, Ação, PAUSA e Observaçao.
No final do loop você exibe a resposta.
Execute somente um passo de cada vês
Use Pensamento para descrever o que você acha que devem ser as ações a serem tomadas.
Use Ação para executar uma das ações disponíveis e então você PAUSA.
Observação será o resultado de executar uma Ação

Ações disponíveis:
{str(calculator)}
{str(wikipedia)}

chat:
Responde questão com informações já conhecidas pelo modelo.
ex: chat: Qual a capital do Brasil?

Exemplo de uma sessão:
Pergunta: Qual a capital da França? <usuário>
Pensamento: Eu devo pesquisar conteudo sobre a França na Wikipedia. <você>
Ação: wikipedia: França <você define qual ação a ser tomada>
PAUSA

Você será chamado novamente com isto:
Observação: França é um país. Sua captial é Paris. <essa informação foi o resultado da ação>

Você então irá retornar:
Resposta: Paris 
"""

action_re = re.compile(r"^Ação: (\w+): (.*)")

def chat(question):
    #chat = ChatbotOpenAI(system="Você responde as questões da maneira mais suscinta possível, sem explicações")
    chat = ChatbotOllama(system="Você responde as questões da maneira mais suscinta possível, sem explicações")
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
    next_prompt = question
    print(f"Respondendo a questão: {question}")
    while i < max_turns:
        i += 1
        result = bot(next_prompt)
        
        print(f"-------------------\n{result}\n-------------------\n")
        if "Resposta:" in result:
            return result
        logging.info(result)
        actions = [action_re.match(a) for a in result.split("\n") if action_re.match(a)]
        logging.info(f"actions: {actions} --> {result}")
        if actions:
            action, input = actions[0].groups()
            if action not in acoes:
                raise Exception(f"Ação não encontrada: {action} {input}")
            logging.info(f"Ação: {action}:{input} - Running")
            obs = acoes[action](input)
            logging.info(f"Observação: {obs}")
            next_prompt = f"Observação: {obs}"
        else:
            return result

def main():
    question = input("Ask a question: ")
    resp = query(question)

if __name__ == '__main__':
    main()

