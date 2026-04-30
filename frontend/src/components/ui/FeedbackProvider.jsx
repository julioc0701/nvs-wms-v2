import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react'
import Button from './Button'

const FeedbackContext = createContext(null)

export function FeedbackProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const [dialog, setDialog] = useState(null)
  const dialogResolveRef = useRef(null)

  const notify = useCallback((message, type = 'info', duration = 3200) => {
    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`
    setToasts(prev => [...prev, { id, message, type }])
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, duration)
  }, [])

  const askConfirm = useCallback((options) => {
    return new Promise((resolve) => {
      dialogResolveRef.current = resolve
      setDialog({
        kind: 'confirm',
        title: options?.title || 'Confirmar ação',
        message: options?.message || 'Deseja continuar?',
        confirmText: options?.confirmText || 'Confirmar',
        cancelText: options?.cancelText || 'Cancelar',
        variant: options?.variant || 'primary',
      })
    })
  }, [])

  const askPrompt = useCallback((options) => {
    return new Promise((resolve) => {
      dialogResolveRef.current = resolve
      setDialog({
        kind: 'prompt',
        title: options?.title || 'Informação',
        message: options?.message || '',
        initialValue: options?.initialValue || '',
        placeholder: options?.placeholder || '',
        confirmText: options?.confirmText || 'Salvar',
        cancelText: options?.cancelText || 'Cancelar',
        variant: options?.variant || 'primary',
      })
    })
  }, [])

  const closeDialog = useCallback((result) => {
    if (dialogResolveRef.current) dialogResolveRef.current(result)
    dialogResolveRef.current = null
    setDialog(null)
  }, [])

  const value = useMemo(() => ({ notify, askConfirm, askPrompt }), [notify, askConfirm, askPrompt])

  return (
    <FeedbackContext.Provider value={value}>
      {children}

      {/* Erros — centralizados na tela, grandes, visíveis para o operador */}
      <div className="fixed inset-x-0 top-1/3 z-[120] flex flex-col items-center gap-3 pointer-events-none px-4">
        {toasts.filter(t => t.type === 'error').map(t => (
          <div
            key={t.id}
            className="rounded-2xl border-2 border-red-300 bg-red-600 text-white px-8 py-5 text-xl font-black shadow-2xl pointer-events-auto text-center w-[min(92vw,480px)]"
          >
            {t.message}
          </div>
        ))}
      </div>

      {/* Outros toasts — canto superior direito */}
      <div className="fixed top-4 right-4 z-[120] flex flex-col gap-2 w-[min(92vw,360px)] pointer-events-none">
        {toasts.filter(t => t.type !== 'error').map(t => (
          <div
            key={t.id}
            className={[
              'rounded-xl border px-4 py-3 text-sm font-semibold shadow-lg pointer-events-auto',
              t.type === 'success' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : '',
              t.type === 'warning' ? 'bg-amber-50 text-amber-700 border-amber-200' : '',
              t.type === 'info' ? 'bg-blue-50 text-blue-700 border-blue-200' : '',
            ].join(' ')}
          >
            {t.message}
          </div>
        ))}
      </div>

      {dialog && (
        <DialogOverlay onClose={() => closeDialog(dialog.kind === 'confirm' ? false : null)}>
          {dialog.kind === 'confirm' ? (
            <ConfirmDialog dialog={dialog} onClose={closeDialog} />
          ) : (
            <PromptDialog dialog={dialog} onClose={closeDialog} />
          )}
        </DialogOverlay>
      )}
    </FeedbackContext.Provider>
  )
}

function DialogOverlay({ children, onClose }) {
  return (
    <div className="fixed inset-0 z-[130] bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="absolute inset-0" onClick={onClose} aria-hidden="true" />
      <div className="relative w-full max-w-md">{children}</div>
    </div>
  )
}

function ConfirmDialog({ dialog, onClose }) {
  return (
    <div className="bg-white border border-slate-200 rounded-2xl shadow-2xl p-6">
      <h3 className="text-lg font-bold text-slate-900">{dialog.title}</h3>
      <p className="text-sm text-slate-500 mt-2">{dialog.message}</p>
      <div className="mt-6 flex gap-2 justify-end">
        <Button onClick={() => onClose(false)}>{dialog.cancelText}</Button>
        <Button variant={dialog.variant === 'danger' ? 'danger' : 'primary'} onClick={() => onClose(true)}>
          {dialog.confirmText}
        </Button>
      </div>
    </div>
  )
}

function PromptDialog({ dialog, onClose }) {
  const [value, setValue] = useState(dialog.initialValue || '')
  return (
    <div className="bg-white border border-slate-200 rounded-2xl shadow-2xl p-6">
      <h3 className="text-lg font-bold text-slate-900">{dialog.title}</h3>
      {dialog.message && <p className="text-sm text-slate-500 mt-2">{dialog.message}</p>}
      <input
        autoFocus
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={dialog.placeholder}
        className="mt-4 w-full rounded-xl border border-slate-300 px-3 py-2 outline-none focus:border-blue-500"
      />
      <div className="mt-6 flex gap-2 justify-end">
        <Button onClick={() => onClose(null)}>{dialog.cancelText}</Button>
        <Button onClick={() => onClose(value)} variant={dialog.variant === 'danger' ? 'danger' : 'primary'}>
          {dialog.confirmText}
        </Button>
      </div>
    </div>
  )
}

export function useFeedback() {
  const ctx = useContext(FeedbackContext)
  if (!ctx) throw new Error('useFeedback must be used inside FeedbackProvider')
  return ctx
}
