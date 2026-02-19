import { Link } from 'react-router-dom'

const CONTACT_EMAIL = 'privacidade@alrea.ai'
const SITE_URL = 'https://chat.alrea.ai'
const EFFECTIVE_DATE = '19 de fevereiro de 2026'

const sections = [
  { id: 'controlador', title: '1. Identificação do controlador' },
  { id: 'dados-coletados', title: '2. Dados coletados' },
  { id: 'finalidade', title: '3. Finalidade do uso dos dados' },
  { id: 'base-legal', title: '4. Base legal (LGPD)' },
  { id: 'compartilhamento', title: '5. Compartilhamento de dados' },
  { id: 'direitos', title: '6. Direitos do titular (Art. 18 LGPD)' },
  { id: 'retencao', title: '7. Retenção de dados' },
  { id: 'seguranca', title: '8. Segurança' },
  { id: 'cookies', title: '9. Cookies e rastreamento' },
  { id: 'atualizacoes', title: '10. Atualizações da política' },
  { id: 'vigencia', title: '11. Data de vigência' },
]

export default function PrivacyPolicyPage() {
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 text-gray-800 dark:text-gray-200">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8 sm:py-12">
        <header className="mb-8">
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white">
            Política de Privacidade
          </h1>
          <p className="mt-2 text-gray-600 dark:text-gray-400">
            Alrea Flow — Plataforma de atendimento ao cliente via WhatsApp
          </p>
        </header>

        <nav className="mb-10 p-4 sm:p-5 rounded-xl bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 shadow-sm">
          <h2 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-3">
            Índice
          </h2>
          <ul className="space-y-2">
            {sections.map(({ id, title }) => (
              <li key={id}>
                <a
                  href={`#${id}`}
                  className="text-blue-600 dark:text-blue-400 hover:underline focus:outline-none focus:ring-2 focus:ring-blue-500 rounded"
                >
                  {title}
                </a>
              </li>
            ))}
          </ul>
        </nav>

        <article className="space-y-8 text-sm sm:text-base leading-relaxed">
          <section id="controlador" className="scroll-mt-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
              1. Identificação do controlador
            </h2>
            <p className="mb-2">
              O controlador dos dados pessoais tratados nesta plataforma é:
            </p>
            <ul className="list-disc pl-5 space-y-1 text-gray-700 dark:text-gray-300">
              <li><strong>Empresa:</strong> RBTec</li>
              <li><strong>Site:</strong> <a href={SITE_URL} className="text-blue-600 dark:text-blue-400 hover:underline" rel="noopener noreferrer" target="_blank">{SITE_URL}</a></li>
              <li><strong>Contato para privacidade:</strong>{' '}
                <a href={`mailto:${CONTACT_EMAIL}`} className="text-blue-600 dark:text-blue-400 hover:underline">{CONTACT_EMAIL}</a>
              </li>
            </ul>
          </section>

          <section id="dados-coletados" className="scroll-mt-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
              2. Dados coletados
            </h2>
            <p className="mb-3">São coletados os seguintes dados, conforme o uso do serviço:</p>
            <ul className="list-disc pl-5 space-y-1 text-gray-700 dark:text-gray-300">
              <li><strong>Dados de contato:</strong> nome, telefone, e-mail</li>
              <li><strong>Mensagens:</strong> conteúdo das conversas realizadas via WhatsApp na plataforma</li>
              <li><strong>Dados de uso:</strong> logs de acesso, endereço IP, tipo de navegador e de dispositivo</li>
              <li><strong>Dados da conta:</strong> nome de usuário e senha (armazenada de forma criptografada)</li>
            </ul>
          </section>

          <section id="finalidade" className="scroll-mt-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
              3. Finalidade do uso dos dados
            </h2>
            <ul className="list-disc pl-5 space-y-1 text-gray-700 dark:text-gray-300">
              <li>Prestação do serviço de atendimento ao cliente via WhatsApp</li>
              <li>Melhoria contínua da plataforma e da experiência do usuário</li>
              <li>Comunicações relacionadas ao serviço (suporte, avisos e atualizações)</li>
            </ul>
          </section>

          <section id="base-legal" className="scroll-mt-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
              4. Base legal (LGPD)
            </h2>
            <p className="mb-2">O tratamento dos dados está fundamentado nas seguintes bases legais:</p>
            <ul className="list-disc pl-5 space-y-1 text-gray-700 dark:text-gray-300">
              <li><strong>Execução de contrato:</strong> para fornecer e operar o serviço contratado</li>
              <li><strong>Legítimo interesse:</strong> para segurança, melhoria do produto e comunicação necessária ao serviço</li>
              <li><strong>Consentimento:</strong> quando aplicável, em casos em que a lei ou a prática exijam consentimento específico</li>
            </ul>
          </section>

          <section id="compartilhamento" className="scroll-mt-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
              5. Compartilhamento de dados
            </h2>
            <p className="mb-2">Os dados podem ser compartilhados com:</p>
            <ul className="list-disc pl-5 space-y-1 text-gray-700 dark:text-gray-300">
              <li><strong>Meta (WhatsApp Business API):</strong> o uso do atendimento via WhatsApp exige o processamento de dados pela Meta, em conformidade com os termos e políticas da WhatsApp Business API.</li>
              <li><strong>Provedores de infraestrutura:</strong> como Railway e demais serviços de hospedagem utilizados para operar a plataforma, sob compromissos de confidencialidade e segurança.</li>
            </ul>
            <p className="mt-3 text-gray-700 dark:text-gray-300">
              <strong>Não vendemos</strong> dados pessoais a terceiros.
            </p>
          </section>

          <section id="direitos" className="scroll-mt-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
              6. Direitos do titular (Art. 18 da LGPD)
            </h2>
            <p className="mb-2">Você pode exercer os seguintes direitos em relação aos seus dados:</p>
            <ul className="list-disc pl-5 space-y-1 text-gray-700 dark:text-gray-300">
              <li>Acesso aos dados</li>
              <li>Correção de dados incompletos ou desatualizados</li>
              <li>Exclusão dos dados</li>
              <li>Portabilidade dos dados</li>
              <li>Revogação do consentimento, quando o tratamento estiver baseado nessa hipótese</li>
            </ul>
            <p className="mt-3 text-gray-700 dark:text-gray-300">
              Para exercer qualquer um desses direitos, entre em contato pelo e-mail{' '}
              <a href={`mailto:${CONTACT_EMAIL}`} className="text-blue-600 dark:text-blue-400 hover:underline">{CONTACT_EMAIL}</a>.
            </p>
          </section>

          <section id="retencao" className="scroll-mt-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
              7. Retenção de dados
            </h2>
            <p className="mb-2">
              Os dados são mantidos pelo tempo necessário à prestação do serviço, ao cumprimento de obrigações legais e à defesa em processos. Critérios de exclusão:
            </p>
            <ul className="list-disc pl-5 space-y-1 text-gray-700 dark:text-gray-300">
              <li>Após o encerramento da conta, os dados podem ser excluídos ou anonimizados conforme nossa política interna e a legislação aplicável.</li>
              <li>Logs e dados técnicos podem ser mantidos por prazos limitados para segurança e auditoria.</li>
            </ul>
          </section>

          <section id="seguranca" className="scroll-mt-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
              8. Segurança
            </h2>
            <p className="mb-2">Adotamos medidas técnicas e organizacionais para proteger os dados, incluindo:</p>
            <ul className="list-disc pl-5 space-y-1 text-gray-700 dark:text-gray-300">
              <li>Criptografia de senhas e de dados sensíveis quando aplicável</li>
              <li>Acesso restrito aos dados apenas a pessoas autorizadas e com necessidade de conhecimento</li>
              <li>Uso de canais seguros (HTTPS) e boas práticas de infraestrutura</li>
            </ul>
          </section>

          <section id="cookies" className="scroll-mt-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
              9. Cookies e rastreamento
            </h2>
            <p className="mb-2">
              Utilizamos cookies e tecnologias semelhantes para: funcionamento da sessão de usuário, preferências e segurança. Cookies essenciais são necessários ao uso da plataforma; outros podem ser configurados conforme avisos exibidos no site.
            </p>
          </section>

          <section id="atualizacoes" className="scroll-mt-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
              10. Atualizações da política
            </h2>
            <p className="text-gray-700 dark:text-gray-300">
              Alterações nesta política serão publicadas nesta página, com indicação da data de atualização. Em mudanças relevantes, podemos notificar por e-mail ou por aviso na plataforma. O uso continuado do serviço após a publicação constitui aceitação das alterações.
            </p>
          </section>

          <section id="vigencia" className="scroll-mt-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
              11. Data de vigência
            </h2>
            <p className="text-gray-700 dark:text-gray-300">
              Esta política está em vigor a partir de <strong>{EFFECTIVE_DATE}</strong>.
            </p>
          </section>
        </article>

        <footer className="mt-12 pt-6 border-t border-gray-200 dark:border-gray-700">
          <Link
            to="/"
            className="inline-flex items-center text-blue-600 dark:text-blue-400 hover:underline font-medium"
          >
            ← Voltar ao sistema
          </Link>
        </footer>
      </div>
    </div>
  )
}
