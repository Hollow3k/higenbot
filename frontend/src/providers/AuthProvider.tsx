import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import type { AuthChangeEvent, Session } from '@supabase/supabase-js'
import { supabase } from '../lib/supabase'

type AuthContextValue = {
  session: Session | null
  loading: boolean
  signUp: typeof supabase.auth.signUp
  signInWithPassword: typeof supabase.auth.signInWithPassword
  signInWithGoogle: () => ReturnType<typeof supabase.auth.signInWithOAuth>
  signOut: () => ReturnType<typeof supabase.auth.signOut>
  getSession: typeof supabase.auth.getSession
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

type AuthProviderProps = {
  children: ReactNode
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let mounted = true

    const syncSession = async () => {
      const { data } = await supabase.auth.getSession()

      if (!mounted) {
        return
      }

      setSession(data.session)
      setLoading(false)
    }

    syncSession()

    const { data } = supabase.auth.onAuthStateChange((_event: AuthChangeEvent, nextSession) => {
      setSession(nextSession)
      setLoading(false)
    })

    return () => {
      mounted = false
      data.subscription.unsubscribe()
    }
  }, [])

  const value: AuthContextValue = {
    session,
    loading,
    signUp: (...args) => supabase.auth.signUp(...args),
    signInWithPassword: (...args) => supabase.auth.signInWithPassword(...args),
    signInWithGoogle: () =>
      supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: window.location.origin,
        },
      }),
    signOut: async () => {
      const result = await supabase.auth.signOut()
      if (!result.error) {
        setSession(null)
      }
      return result
    },
    getSession: (...args) => supabase.auth.getSession(...args),
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)

  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }

  return context
}
