import * as RT from '@radix-ui/react-tooltip'

export function Tooltip({ content, children }) {
  if (!content) return children
  return (
    <RT.Provider delayDuration={200}>
      <RT.Root>
        <RT.Trigger asChild>{children}</RT.Trigger>
        <RT.Portal>
          <RT.Content className="rounded bg-slate-900 text-white text-xs px-2 py-1 max-w-xs shadow-lg z-50" sideOffset={4}>
            {content}
            <RT.Arrow className="fill-slate-900" />
          </RT.Content>
        </RT.Portal>
      </RT.Root>
    </RT.Provider>
  )
}
