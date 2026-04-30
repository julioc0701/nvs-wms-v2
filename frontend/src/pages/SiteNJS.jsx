import { useMemo, useRef, useState } from 'react'
import {
  ArrowRight,
  Bot,
  BrainCircuit,
  CheckCircle2,
  CircleAlert,
  Database,
  FileSearch,
  GitBranch,
  MessageCircle,
  MousePointer2,
  Network,
  Route,
  ScanLine,
  Sparkles,
  Workflow,
  Zap,
} from 'lucide-react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { useGSAP } from '@gsap/react'

gsap.registerPlugin(ScrollTrigger, useGSAP)

const whatsappMessage =
  'Oi, vi o site da NJS e quero agendar um diagnostico para mapear oportunidades de IA, agentes e automacao na minha empresa.'
const WHATSAPP_URL = `https://wa.me/5519991246031?text=${encodeURIComponent(whatsappMessage)}`

const flowStages = [
  {
    id: 'mapear',
    kicker: '01 / mapa atual',
    title: 'Sentamos com sua equipe e desenhamos como o processo funciona hoje.',
    copy: 'Nada de comecar pela ferramenta. Primeiro entendemos tarefas, decisoes, sistemas, planilhas e conversas que sustentam a operacao.',
    chip: 'Processo atual',
  },
  {
    id: 'gargalos',
    kicker: '02 / gargalos',
    title: 'O fluxo revela onde tempo, dados e energia estao vazando.',
    copy: 'Atrasos, retrabalho, relatorios manuais, dados duplicados e follow-ups esquecidos aparecem como pontos de friccao.',
    chip: 'Diagnostico NJS',
  },
  {
    id: 'ia',
    kicker: '03 / ganho com IA',
    title: 'Marcamos onde agentes e automacoes podem gerar ganho real.',
    copy: 'IA entra onde faz sentido: classificar, resumir, responder, alertar, integrar, gerar relatorios e apoiar decisoes.',
    chip: 'Oportunidade',
  },
  {
    id: 'operar',
    kicker: '04 / implementacao',
    title: 'O processo vira um sistema mais claro, conectado e operavel.',
    copy: 'Agentes, APIs, dashboards e automacoes entram sob controle humano, conectados ao que sua empresa ja usa.',
    chip: 'Fluxo implementado',
  },
]

const flowBlocks = [
  { id: 'entrada', label: 'Pedido do cliente', type: 'manual', x: 8, y: 42, icon: MessageCircle },
  { id: 'planilha', label: 'Planilha manual', type: 'pain', x: 27, y: 22, icon: Database },
  { id: 'atendimento', label: 'Atendimento', type: 'manual', x: 29, y: 64, icon: MousePointer2 },
  { id: 'diagnostico', label: 'Diagnostico NJS', type: 'scan', x: 50, y: 43, icon: ScanLine },
  { id: 'agente', label: 'Agente IA', type: 'agent', x: 68, y: 24, icon: Bot },
  { id: 'automacao', label: 'Automacao + API', type: 'agent', x: 70, y: 64, icon: Zap },
  { id: 'resultado', label: 'Fluxo operando', type: 'result', x: 90, y: 43, icon: CheckCircle2 },
]

const paths = [
  'M12 45 C18 45 20 27 26 26',
  'M12 45 C18 45 20 64 28 64',
  'M32 26 C40 27 43 39 49 42',
  'M33 64 C41 63 44 49 49 44',
  'M54 41 C60 34 62 26 67 25',
  'M54 45 C60 54 62 63 69 64',
  'M74 25 C82 28 84 39 89 42',
  'M75 64 C83 61 84 49 89 45',
]

const opportunities = [
  ['Atendimento', 'Agente responde com base em documentos e historico.'],
  ['Relatorios', 'Automacao coleta dados e gera resumo operacional.'],
  ['Financeiro', 'IA classifica documentos, aponta pendencias e cria alertas.'],
  ['Comercial', 'Copiloto gera proposta, e-mail e follow-up com contexto.'],
]

const techStack = ['ChatGPT', 'OpenAI', 'Claude', 'Modelos open source', 'n8n', 'Make', 'APIs', 'Dashboards']

function LogoMark() {
  return (
    <div className="flex items-center gap-3">
      <div className="relative grid h-11 w-11 place-items-center rounded-xl border border-[#A8D7FF] bg-white shadow-[0_16px_40px_rgba(8,34,74,.12)]">
        <svg viewBox="0 0 64 64" className="h-9 w-9" fill="none" aria-hidden="true">
          <path d="M13 46V18l19 28V18" stroke="#08224A" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M40 18h8c5 0 8 3 8 7s-3 7-8 7h-4c-5 0-8 3-8 8v6" stroke="#2F80ED" strokeWidth="5" strokeLinecap="round" />
          <circle cx="13" cy="46" r="3" fill="#8EC5FF" />
          <circle cx="32" cy="46" r="3" fill="#2F80ED" />
          <circle cx="49" cy="18" r="3" fill="#8EC5FF" />
        </svg>
      </div>
      <div>
        <div className="text-xl font-black leading-none text-[#061A3A]">NJS</div>
        <div className="mt-1 text-[10px] font-black uppercase tracking-[0.2em] text-[#2F80ED]">Novais Julio System</div>
      </div>
    </div>
  )
}

function CTAButton({ children = 'Agendar diagnostico de IA', dark = false }) {
  return (
    <a
      href={WHATSAPP_URL}
      target="_blank"
      rel="noopener noreferrer"
      className={`inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-xl px-5 py-3 text-center text-sm font-black transition hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#8EC5FF] sm:w-auto ${
        dark
          ? 'bg-[#061A3A] text-white shadow-[0_18px_45px_rgba(6,26,58,.22)] hover:bg-[#0A2F66]'
          : 'bg-white text-[#061A3A] shadow-[0_18px_45px_rgba(255,255,255,.22)] hover:bg-[#DDEEFF]'
      }`}
    >
      {children}
      <ArrowRight className="h-4 w-4" />
    </a>
  )
}

function FlowBlock({ block, index }) {
  const Icon = block.icon
  return (
    <div
      className={`flow-block flow-${block.type} absolute z-20 w-[148px] -translate-x-1/2 -translate-y-1/2 rounded-xl border p-3 shadow-[0_18px_48px_rgba(8,34,74,.12)] backdrop-blur-md`}
      style={{ left: `${block.x}%`, top: `${block.y}%`, '--d': `${index * 0.12}s` }}
    >
      <div className="flex items-center gap-2">
        <span className="grid h-8 w-8 place-items-center rounded-lg bg-[#DDEEFF] text-[#08224A]">
          <Icon className="h-4 w-4" />
        </span>
        <span className="text-sm font-black leading-tight text-[#061A3A]">{block.label}</span>
      </div>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-[#DDEEFF]">
        <span className="data-packet block h-full w-1/2 rounded-full bg-[#2F80ED]" />
      </div>
      {block.type === 'pain' && (
        <span className="absolute -right-2 -top-2 grid h-7 w-7 place-items-center rounded-full bg-[#FFE8C2] text-[#9A4A00] shadow-[0_0_0_6px_rgba(255,232,194,.45)]">
          <CircleAlert className="h-4 w-4" />
        </span>
      )}
    </div>
  )
}

function ProcessFlowScene() {
  return (
    <div className="flow-shell relative min-h-[500px] overflow-hidden rounded-[1.5rem] border border-[#B7DCFF] bg-white shadow-[0_35px_110px_rgba(8,34,74,.12)]">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_45%,rgba(142,197,255,.34),transparent_32%),linear-gradient(180deg,#F8FBFF_0%,#EAF5FF_100%)]" />
      <div className="blueprint-grid absolute inset-0 opacity-80" />
      <div className="scan-band absolute inset-y-0 left-0 z-10 w-1/4 bg-gradient-to-r from-transparent via-[#8EC5FF]/35 to-transparent" />

      <svg className="absolute inset-0 z-10 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        {paths.map((path, index) => (
          <path key={path} className="flow-path" style={{ '--d': `${index * 0.16}s` }} d={path} />
        ))}
      </svg>

      <div className="absolute left-1/2 top-1/2 z-10 h-[74%] w-[86%] -translate-x-1/2 -translate-y-1/2 rounded-[50%] border border-[#A8D7FF]/70" />
      <div className="absolute left-1/2 top-1/2 z-10 h-[46%] w-[56%] -translate-x-1/2 -translate-y-1/2 rounded-[50%] border border-[#A8D7FF]/50" />

      {flowBlocks.map((block, index) => (
        <FlowBlock key={block.id} block={block} index={index} />
      ))}

      <div className="absolute bottom-5 left-5 right-5 z-30 grid gap-3 rounded-xl border border-[#B7DCFF] bg-white/88 p-4 shadow-[0_18px_50px_rgba(8,34,74,.10)] backdrop-blur-xl md:left-auto md:w-[430px]">
        <div className="flex items-center justify-between gap-3">
          <span className="font-mono text-[10px] font-black uppercase tracking-[.22em] text-[#2F80ED]">fluxo vivo</span>
          <span className="rounded-full bg-[#DDEEFF] px-3 py-1 text-xs font-black text-[#08224A]">NJS scan ativo</span>
        </div>
        <p className="text-lg font-black leading-snug text-[#061A3A]">
          O desenho mostra onde a operacao perde tempo e onde a IA pode entrar com controle.
        </p>
      </div>
    </div>
  )
}

function StoryRail({ activeStage }) {
  return (
    <div className="sticky top-24 hidden h-[calc(100vh-8rem)] flex-col justify-center gap-4 lg:flex">
      {flowStages.map((stage, index) => (
        <div key={stage.id} className={`rail-step rounded-xl border p-4 transition ${activeStage === index ? 'border-[#2F80ED] bg-white shadow-[0_18px_40px_rgba(8,34,74,.10)]' : 'border-[#CFE7FF] bg-white/45'}`}>
          <div className="font-mono text-[10px] font-black uppercase tracking-[.2em] text-[#2F80ED]">{stage.kicker}</div>
          <div className="mt-2 text-sm font-black text-[#061A3A]">{stage.chip}</div>
        </div>
      ))}
    </div>
  )
}

function StageCard({ stage, index }) {
  return (
    <article className="stage-card min-h-[72vh] rounded-[1.5rem] border border-[#CFE7FF] bg-white/82 p-6 shadow-[0_22px_70px_rgba(8,34,74,.10)] backdrop-blur-md md:p-8 lg:min-h-[68vh]">
      <div className="font-mono text-xs font-black uppercase tracking-[.24em] text-[#2F80ED]">{stage.kicker}</div>
      <h2 className="mt-5 max-w-3xl text-4xl font-black leading-[.96] tracking-[-.04em] text-[#061A3A] md:text-6xl">{stage.title}</h2>
      <p className="mt-6 max-w-2xl text-lg leading-8 text-[#24415F]">{stage.copy}</p>
      <div className="mt-8 inline-flex items-center gap-2 rounded-full border border-[#A8D7FF] bg-[#DDEEFF] px-4 py-2 text-sm font-black text-[#08224A]">
        <Sparkles className="h-4 w-4" />
        {stage.chip}
      </div>
      {index === 2 && (
        <div className="mt-8 grid gap-3 sm:grid-cols-2">
          {opportunities.map(([title, copy]) => (
            <div key={title} className="rounded-xl border border-[#CFE7FF] bg-[#F8FBFF] p-4">
              <div className="text-base font-black text-[#061A3A]">{title}</div>
              <p className="mt-2 text-sm leading-6 text-[#46637F]">{copy}</p>
            </div>
          ))}
        </div>
      )}
    </article>
  )
}

export default function SiteNJS() {
  const pageRef = useRef(null)
  const sceneRef = useRef(null)
  const [activeStage, setActiveStage] = useState(0)

  const stageLabels = useMemo(() => flowStages.map((stage) => stage.chip), [])

  useGSAP(() => {
    const ctx = gsap.context(() => {
      gsap.utils.toArray('.stage-card').forEach((card, index) => {
        ScrollTrigger.create({
          trigger: card,
          start: 'top center',
          end: 'bottom center',
          onEnter: () => setActiveStage(index),
          onEnterBack: () => setActiveStage(index),
        })
      })

      const mm = gsap.matchMedia()
      mm.add('(min-width: 1024px)', () => {
        gsap.to('.flow-camera', {
          yPercent: -11,
          scale: 1.08,
          rotateX: 4,
          ease: 'none',
          scrollTrigger: {
            trigger: '.flow-experience',
            start: 'top top',
            end: 'bottom bottom',
            scrub: 0.7,
          },
        })

        gsap.to('.flow-path', {
          strokeDashoffset: -540,
          ease: 'none',
          scrollTrigger: {
            trigger: '.flow-experience',
            start: 'top top',
            end: 'bottom bottom',
            scrub: 0.8,
          },
        })
      })

      return () => mm.revert()
    }, pageRef)

    return () => ctx.revert()
  }, { scope: pageRef })

  const handlePointerMove = (event) => {
    if (!sceneRef.current) return
    const rect = sceneRef.current.getBoundingClientRect()
    const x = (event.clientX - rect.left) / rect.width - 0.5
    const y = (event.clientY - rect.top) / rect.height - 0.5
    sceneRef.current.style.setProperty('--rx', `${y * -7}deg`)
    sceneRef.current.style.setProperty('--ry', `${x * 9}deg`)
  }

  return (
    <main ref={pageRef} className="njs-page min-h-screen overflow-hidden bg-[#F8FBFF] text-[#061A3A]">
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Manrope:wght@400;500;600;700;800&family=JetBrains+Mono:wght@600;700&display=swap');
        .njs-page { font-family: 'Manrope', system-ui, sans-serif; overflow-x: hidden; }
        .display-serif { font-family: 'Instrument Serif', Georgia, serif; }
        .font-mono { font-family: 'JetBrains Mono', monospace; }
        html { scroll-behavior: smooth; }
        .blueprint-grid {
          background-image:
            linear-gradient(rgba(47,128,237,.13) 1px, transparent 1px),
            linear-gradient(90deg, rgba(47,128,237,.13) 1px, transparent 1px);
          background-size: 34px 34px;
          mask-image: radial-gradient(circle at 50% 45%, #000 0%, transparent 78%);
        }
        .flow-shell { transform: rotateX(var(--rx, 0deg)) rotateY(var(--ry, 0deg)); transform-style: preserve-3d; transition: transform .18s ease-out; }
        .flow-path {
          fill: none;
          stroke: rgba(47,128,237,.62);
          stroke-width: .48;
          stroke-linecap: round;
          stroke-dasharray: 10 10;
          stroke-dashoffset: 0;
          filter: drop-shadow(0 0 8px rgba(142,197,255,.55));
          animation: pathFlow 6s linear infinite;
        }
        .flow-block { background: rgba(255,255,255,.82); animation: blockFloat 5s ease-in-out infinite; animation-delay: var(--d); }
        .wordmark-outline {
          color: transparent;
          -webkit-text-stroke: 1px rgba(8,34,74,.08);
          text-stroke: 1px rgba(8,34,74,.08);
        }
        .flow-pain { border-color: #FFD89A; }
        .flow-scan { border-color: #2F80ED; box-shadow: 0 18px 60px rgba(47,128,237,.20); }
        .flow-agent { border-color: #8EC5FF; background: rgba(221,238,255,.9); }
        .flow-result { border-color: #08224A; box-shadow: 0 18px 60px rgba(8,34,74,.18); }
        .scan-band { animation: scanPass 5.4s ease-in-out infinite; }
        .data-packet { animation: packet 2.4s ease-in-out infinite; }
        .flow-camera { transform-origin: 50% 50%; }
        @keyframes pathFlow { to { stroke-dashoffset: -120; } }
        @keyframes scanPass {
          0% { transform: translateX(-130%); opacity: 0; }
          18%, 72% { opacity: 1; }
          100% { transform: translateX(430%); opacity: 0; }
        }
        @keyframes packet {
          0% { transform: translateX(-120%); opacity: 0; }
          25%, 80% { opacity: 1; }
          100% { transform: translateX(240%); opacity: 0; }
        }
        @keyframes blockFloat {
          0%, 100% { transform: translate(-50%, -50%) translateY(0); }
          50% { transform: translate(-50%, -50%) translateY(-7px); }
        }
        @media (max-width: 767px) {
          .njs-page, .njs-page section, .njs-page header { max-width: 100vw; overflow-x: hidden; }
          .hero-copy, .hero-copy p, .hero-copy h1, .hero-copy a { max-width: min(326px, calc(100vw - 64px)); }
          .flow-shell { min-height: 560px; transform: none !important; }
          .flow-block { width: 126px; padding: .65rem; }
          .flow-block span { font-size: .72rem; }
        }
        @media (prefers-reduced-motion: reduce) {
          *, *:before, *:after { animation: none !important; transition: none !important; scroll-behavior: auto !important; }
        }
      `}</style>

      <header className="fixed left-0 right-0 top-0 z-50 border-b border-[#DDEEFF]/80 bg-white/82 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4 md:px-8">
          <LogoMark />
          <nav className="hidden items-center gap-2 rounded-full border border-[#DDEEFF] bg-[#F8FBFF] p-1 lg:flex">
            {stageLabels.map((label, index) => (
              <a key={label} href={`#stage-${index}`} className="rounded-full px-4 py-2 text-xs font-black text-[#24415F] transition hover:bg-white hover:text-[#061A3A]">
                {String(index + 1).padStart(2, '0')} {label}
              </a>
            ))}
          </nav>
          <div className="hidden sm:block">
            <CTAButton dark>Conversar</CTAButton>
          </div>
        </div>
      </header>

      <section className="relative min-h-screen overflow-hidden px-5 pb-16 pt-28 md:px-8">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_18%_14%,rgba(142,197,255,.46),transparent_28%),radial-gradient(circle_at_85%_10%,rgba(221,238,255,.9),transparent_30%),linear-gradient(180deg,#FFFFFF_0%,#F8FBFF_54%,#EAF5FF_100%)]" />
        <div className="wordmark-outline pointer-events-none absolute -bottom-8 left-1/2 hidden -translate-x-1/2 whitespace-nowrap text-[12vw] italic leading-none md:block">
          NOVAIS JULIO SYSTEM
        </div>
        <div className="relative z-10 mx-auto grid max-w-7xl gap-12 lg:grid-cols-[.88fr_1.12fr] lg:items-center">
          <div className="hero-copy min-w-0">
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-[#B7DCFF] bg-white px-4 py-2 text-xs font-black uppercase tracking-[.22em] text-[#2F80ED] shadow-[0_12px_35px_rgba(8,34,74,.08)]">
              <Workflow className="h-4 w-4" />
              Consultoria de IA - atendimento direto
            </div>
            <h1 className="max-w-4xl break-words text-[3rem] font-black leading-[.9] tracking-[-.04em] text-[#061A3A] sm:text-[3.7rem] md:text-[5.75rem] md:leading-[.86]">
              Sua empresa pode mais.
              <span className="display-serif mt-1 block font-normal italic tracking-normal text-[#0B68FF]">A NJS mostra como.</span>
            </h1>
            <p className="mt-7 max-w-full break-words text-base leading-8 text-[#314A66] sm:max-w-2xl md:text-xl">
              Sentamos com voce, desenhamos seu processo, encontramos gargalos e implementamos IA, agentes e automacoes onde elas realmente geram resultado.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <CTAButton dark>Agendar conversa</CTAButton>
              <a href="#fluxo" className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-xl border border-[#B7DCFF] bg-white px-5 py-3 text-sm font-black text-[#0B68FF] transition hover:-translate-y-0.5 hover:bg-[#DDEEFF] sm:w-auto">
                Como funciona
                <ArrowRight className="h-4 w-4" />
              </a>
            </div>
            <p className="display-serif mt-10 max-w-xl text-xl italic leading-8 text-[#294461]">
              "Trinta minutos de conversa podem mudar como sua empresa trabalha pelos proximos cinco anos."
            </p>
          </div>

          <div ref={sceneRef} onPointerMove={handlePointerMove} className="flow-camera min-w-0">
            <ProcessFlowScene />
          </div>
        </div>
      </section>

      <section className="relative overflow-hidden bg-[#061A3A] px-5 py-16 text-white md:px-8">
        <div className="absolute inset-0 opacity-20 [background-image:linear-gradient(rgba(142,197,255,.2)_1px,transparent_1px),linear-gradient(90deg,rgba(142,197,255,.2)_1px,transparent_1px)] [background-size:42px_42px]" />
        <div className="relative mx-auto grid max-w-7xl gap-8 lg:grid-cols-[.9fr_1.1fr] lg:items-end">
          <div>
            <div className="font-mono text-xs font-black uppercase tracking-[.24em] text-[#8EC5FF]">a tese da NJS</div>
            <h2 className="mt-4 max-w-3xl text-4xl font-black leading-[.96] tracking-[-.04em] md:text-6xl">
              Antes de vender IA, a gente entende a operacao.
            </h2>
          </div>
          <p className="max-w-2xl text-lg leading-8 text-[#DDEEFF]">
            O diferencial nao e colocar um chatbot em qualquer lugar. E mapear como o trabalho acontece, achar o ponto certo de ganho e implementar uma solucao que a equipe consegue usar.
          </p>
        </div>
      </section>

      <section id="fluxo" className="flow-experience relative bg-[#EAF5FF] px-5 py-20 md:px-8">
        <div className="mx-auto grid max-w-7xl gap-8 lg:grid-cols-[260px_1fr]">
          <StoryRail activeStage={activeStage} />
          <div className="grid gap-10">
            {flowStages.map((stage, index) => (
              <div id={`stage-${index}`} key={stage.id}>
                <StageCard stage={stage} index={index} />
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="px-5 py-20 md:px-8">
        <div className="mx-auto max-w-7xl">
          <div className="max-w-3xl">
            <div className="font-mono text-xs font-black uppercase tracking-[.24em] text-[#2F80ED]">onde aplicamos</div>
            <h2 className="mt-4 text-4xl font-black leading-[.96] tracking-[-.04em] text-[#061A3A] md:text-6xl">
              IA como camada de operacao, nao como promessa vazia.
            </h2>
          </div>
          <div className="mt-10 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {[
              [FileSearch, 'Documentos', 'Agentes consultam politicas, contratos e manuais.'],
              [BrainCircuit, 'Decisoes', 'IA resume dados e apoia priorizacao com contexto.'],
              [Route, 'Rotinas', 'Automacoes executam tarefas repetitivas e alertas.'],
              [Network, 'Integracoes', 'APIs conectam CRM, ERP, planilhas e canais.'],
            ].map(([Icon, title, copy]) => (
              <article key={title} className="rounded-2xl border border-[#CFE7FF] bg-white p-6 shadow-[0_18px_55px_rgba(8,34,74,.08)] transition hover:-translate-y-1 hover:border-[#8EC5FF]">
                <div className="grid h-12 w-12 place-items-center rounded-xl bg-[#DDEEFF] text-[#08224A]">
                  <Icon className="h-6 w-6" />
                </div>
                <h3 className="mt-5 text-xl font-black text-[#061A3A]">{title}</h3>
                <p className="mt-3 leading-7 text-[#46637F]">{copy}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="px-5 pb-20 md:px-8">
        <div className="mx-auto grid max-w-7xl gap-8 rounded-[1.75rem] bg-[#061A3A] p-8 text-white shadow-[0_35px_110px_rgba(8,34,74,.22)] md:p-12 lg:grid-cols-[1fr_auto] lg:items-center">
          <div>
            <div className="font-mono text-xs font-black uppercase tracking-[.24em] text-[#8EC5FF]">proximo passo</div>
            <h2 className="mt-4 max-w-4xl text-4xl font-black leading-[.96] tracking-[-.04em] md:text-6xl">
              Vamos desenhar o fluxo atual da sua empresa e achar o primeiro ganho com IA.
            </h2>
            <div className="mt-7 flex flex-wrap gap-2">
              {techStack.map((tech) => (
                <span key={tech} className="rounded-full border border-[#8EC5FF]/30 bg-white/8 px-4 py-2 text-sm font-black text-[#DDEEFF]">
                  {tech}
                </span>
              ))}
            </div>
          </div>
          <CTAButton>Agendar diagnostico</CTAButton>
        </div>
      </section>

      <footer className="border-t border-[#DDEEFF] bg-white px-5 py-8 text-center text-xs leading-6 text-[#46637F] md:px-8">
        <p>NJS - Novais Julio System. Consultoria em IA, agentes e automacao.</p>
        <p className="mt-2">
          Marcas e nomes citados pertencem aos seus respectivos proprietarios. O uso indica experiencia tecnica ou compatibilidade, nao parceria oficial.
        </p>
      </footer>
    </main>
  )
}
