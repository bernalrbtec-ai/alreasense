/**
 * Página de ajuda: instruções para integração (fluxos Typebot e agentes Dify).
 * Documenta instruções de controle no texto e variáveis para parâmetros de entrada.
 */
import { Link } from 'react-router-dom'
import { BookOpen, ArrowLeft, Zap, Bot } from 'lucide-react'
import { Card } from '../components/ui/Card'

function CodeBlock({ children }: { children: React.ReactNode }) {
  return (
    <pre className="bg-gray-100 dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-lg p-4 text-sm font-mono text-gray-800 dark:text-gray-200 overflow-x-auto">
      {children}
    </pre>
  )
}

function InlineCode({ children }: { children: React.ReactNode }) {
  return (
    <code className="bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded text-sm font-mono text-gray-800 dark:text-gray-200">
      {children}
    </code>
  )
}

export default function IntegracaoInstrucoesPage() {
  return (
    <div className="space-y-8 max-w-4xl">
      <div className="flex items-center gap-4">
        <Link
          to="/configurations"
          className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100"
        >
          <ArrowLeft className="h-4 w-4" />
          Voltar às Configurações
        </Link>
      </div>

      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
          <BookOpen className="h-7 w-7" />
          Instruções para integração
        </h1>
        <p className="mt-2 text-gray-600 dark:text-gray-400">
          Use estas instruções em fluxos (Typebot) e em agentes Dify para encerrar conversas, transferir para departamentos
          e passar contexto dinâmico. O texto é técnico mas pensado para quem integra.
        </p>
      </div>

      {/* Seção 1: Instruções de controle */}
      <Card className="p-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2 mb-4">
          <Zap className="h-5 w-5" />
          1. Instruções de controle no texto da resposta
        </h2>
        <p className="text-gray-600 dark:text-gray-400 mb-4">
          O Sense interpreta trechos no formato <InlineCode>#&#123;&quot;chave&quot;: valor&#125;</InlineCode> na
          resposta do bot ou do agente. Esse trecho é removido antes de enviar a mensagem ao cliente e dispara a ação
          correspondente (encerrar ou transferir). Funciona em <strong>Typebot</strong> e em <strong>agentes Dify</strong>.
        </p>

        <h3 className="text-base font-medium text-gray-900 dark:text-gray-100 mt-4 mb-2">Onde usar</h3>
        <ul className="list-disc list-inside text-gray-600 dark:text-gray-400 text-sm space-y-1 mb-4">
          <li><strong>Typebot:</strong> inclua o JSON no texto da mensagem de um bloco (ex.: nó &quot;Mensagem&quot; ou &quot;Text&quot;). O Sense interpreta ao receber a resposta do fluxo.</li>
          <li><strong>Dify:</strong> inclua o JSON no texto de saída do agente (ex.: na resposta final do assistente).</li>
        </ul>

        <h3 className="text-base font-medium text-gray-900 dark:text-gray-100 mt-6 mb-2">Encerrar conversa</h3>
        <p className="text-gray-600 dark:text-gray-400 mb-2">
          Chaves aceitas: <InlineCode>closeTicket</InlineCode>, <InlineCode>encerrar</InlineCode>,{' '}
          <InlineCode>closeConversation</InlineCode>. Valor deve ser <InlineCode>true</InlineCode>.
        </p>
        <CodeBlock>{'#{"closeTicket": true}'}</CodeBlock>
        <p className="text-sm text-gray-500 dark:text-gray-500 mt-2">
          Exemplo em uma resposta: &quot;Obrigado pelo contato! #&#123;&quot;closeTicket&quot;: true&#125;&quot; — o cliente vê só &quot;Obrigado pelo contato!&quot; e a conversa é fechada.
        </p>

        <h3 className="text-base font-medium text-gray-900 dark:text-gray-100 mt-6 mb-2">Transferir para departamento</h3>
        <p className="text-gray-600 dark:text-gray-400 mb-2">
          Chaves: <InlineCode>transferTo</InlineCode> ou <InlineCode>transferToDepartment</InlineCode>. Valor: nome do departamento (exatamente como cadastrado no Sense).
        </p>
        <CodeBlock>{'#{"transferTo": "Comercial"}'}</CodeBlock>
        <p className="text-sm text-gray-500 dark:text-gray-500 mt-2">
          A conversa é transferida para o departamento cujo nome corresponde (sem diferenciar maiúsculas/minúsculas).
        </p>

        <h3 className="text-base font-medium text-gray-900 dark:text-gray-100 mt-6 mb-2">Transferir com resumo para o operador</h3>
        <p className="text-gray-600 dark:text-gray-400 mb-2">
          Use <InlineCode>summary</InlineCode> ou <InlineCode>resumo</InlineCode> no mesmo JSON. O resumo aparece no bubble de transferência para quem está no painel.
        </p>
        <CodeBlock>{'#{"transferTo": "Suporte", "summary": "Cliente solicitou reembolso do pedido #12345"}'}</CodeBlock>
        <p className="text-sm text-gray-500 dark:text-gray-500 mt-2">
          O resumo é truncado a 500 caracteres e normalizado em uma linha. Use texto curto e objetivo.
        </p>

        <h3 className="text-base font-medium text-gray-900 dark:text-gray-100 mt-4 mb-2">Boas práticas</h3>
        <ul className="list-disc list-inside text-gray-600 dark:text-gray-400 text-sm space-y-1">
          <li>Uma instrução por trecho; o JSON deve ser válido.</li>
          <li>Nome do departamento igual ao cadastrado (ex.: &quot;Comercial&quot;, &quot;Suporte&quot;).</li>
          <li>Resumo opcional; se omitir, a transferência funciona normalmente.</li>
        </ul>
      </Card>

      {/* Seção 2: Variáveis para parâmetros de entrada (Dify) */}
      <Card className="p-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2 mb-4">
          <Bot className="h-5 w-5" />
          2. Variáveis para parâmetros de entrada (agentes Dify)
        </h2>
        <p className="text-gray-600 dark:text-gray-400 mb-4">
          Nos campos de entrada dos agentes Dify (Configurações &gt; IA &gt; Dify &gt; Parâmetros de entrada), você pode usar
          as variáveis abaixo. Elas são substituídas no momento da chamada pelo valor da conversa atual.
        </p>

        <div className="overflow-x-auto">
          <table className="min-w-full text-sm border border-gray-200 dark:border-gray-600 rounded-lg overflow-hidden">
            <thead className="bg-gray-50 dark:bg-gray-700">
              <tr>
                <th className="px-4 py-2 text-left font-medium text-gray-900 dark:text-gray-100">Variável</th>
                <th className="px-4 py-2 text-left font-medium text-gray-900 dark:text-gray-100">Descrição</th>
                <th className="px-4 py-2 text-left font-medium text-gray-900 dark:text-gray-100">Exemplo de valor</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-600 bg-white dark:bg-gray-800">
              <tr>
                <td className="px-4 py-2 font-mono text-blue-600 dark:text-blue-400">{'{{tenant_name}}'}</td>
                <td className="px-4 py-2 text-gray-600 dark:text-gray-400">Nome do tenant (empresa/unidade)</td>
                <td className="px-4 py-2 text-gray-500 dark:text-gray-500">Minha Empresa</td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-mono text-blue-600 dark:text-blue-400">{'{{contact_name}}'}</td>
                <td className="px-4 py-2 text-gray-600 dark:text-gray-400">Nome do contato na conversa</td>
                <td className="px-4 py-2 text-gray-500 dark:text-gray-500">João Silva</td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-mono text-blue-600 dark:text-blue-400">{'{{contact_phone}}'}</td>
                <td className="px-4 py-2 text-gray-600 dark:text-gray-400">Telefone do contato</td>
                <td className="px-4 py-2 text-gray-500 dark:text-gray-500">+5511999999999</td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-mono text-blue-600 dark:text-blue-400">{'{{conversation_id}}'}</td>
                <td className="px-4 py-2 text-gray-600 dark:text-gray-400">ID da conversa no Sense (UUID)</td>
                <td className="px-4 py-2 text-gray-500 dark:text-gray-500">abc-123-def-456...</td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-mono text-blue-600 dark:text-blue-400">{'{{department_name}}'}</td>
                <td className="px-4 py-2 text-gray-600 dark:text-gray-400">Nome do departamento atual (vazio se Inbox)</td>
                <td className="px-4 py-2 text-gray-500 dark:text-gray-500">Comercial</td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-mono text-blue-600 dark:text-blue-400">{'{{is_open}}'}</td>
                <td className="px-4 py-2 text-gray-600 dark:text-gray-400">Dentro do horário de funcionamento (string)</td>
                <td className="px-4 py-2 text-gray-500 dark:text-gray-500">true ou false</td>
              </tr>
            </tbody>
          </table>
        </div>

        <h3 className="text-base font-medium text-gray-900 dark:text-gray-100 mt-6 mb-2">Exemplo de uso nos parâmetros</h3>
        <p className="text-gray-600 dark:text-gray-400 mb-2">
          No Dify, em um campo de texto de contexto, você pode preencher:
        </p>
        <CodeBlock>{'Atendendo {{contact_name}} ({{contact_phone}}) no departamento {{department_name}}. Horário de funcionamento: {{is_open}}.'}</CodeBlock>
        <p className="text-sm text-gray-500 dark:text-gray-500 mt-2">
          Na chamada, o Sense substitui cada variável pelo valor da conversa (ex.: &quot;Atendendo João Silva (+5511999999999) no departamento Comercial. Horário de funcionamento: true.&quot;).
        </p>
      </Card>
    </div>
  )
}
