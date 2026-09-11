import { useEffect, useState } from 'react'
import './App.css'

// In production, nginx (see frontend/nginx.conf) proxies /api/* to the
// backend Service inside the cluster, so a relative path works both in
// Kubernetes and in local `npm run dev` (via the Vite proxy, see vite.config.js).
const API_BASE = '/api'

function App() {
  const [items, setItems] = useState([])
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  const fetchItems = async () => {
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/items`)
      if (!res.ok) throw new Error(`Server responded ${res.status}`)
      const data = await res.json()
      setItems(data)
    } catch (err) {
      setError('Could not reach the backend API. Is it running?')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchItems()
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!name.trim()) return
    setSubmitting(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/items`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description }),
      })
      if (!res.ok) throw new Error(`Server responded ${res.status}`)
      setName('')
      setDescription('')
      await fetchItems()
    } catch (err) {
      setError('Could not save the item. Please try again.')
      console.error(err)
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async (id) => {
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/items/${id}`, { method: 'DELETE' })
      if (!res.ok) throw new Error(`Server responded ${res.status}`)
      setItems((prev) => prev.filter((item) => item.id !== id))
    } catch (err) {
      setError('Could not delete the item. Please try again.')
      console.error(err)
    }
  }

  return (
    <div className="page">
      <header>
        <h1>Items</h1>
        <p className="subtitle">React frontend &rarr; Flask API &rarr; PostgreSQL</p>
      </header>

      <form className="item-form" onSubmit={handleSubmit}>
        <input
          type="text"
          placeholder="Item name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <input
          type="text"
          placeholder="Description (optional)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
        <button type="submit" disabled={submitting}>
          {submitting ? 'Adding…' : 'Add item'}
        </button>
      </form>

      {error && <div className="error-banner">{error}</div>}

      {loading ? (
        <p className="empty-state">Loading items…</p>
      ) : items.length === 0 ? (
        <p className="empty-state">No items yet — add one above.</p>
      ) : (
        <ul className="item-list">
          {items.map((item) => (
            <li key={item.id} className="item-row">
              <div>
                <div className="item-name">{item.name}</div>
                {item.description && (
                  <div className="item-description">{item.description}</div>
                )}
              </div>
              <button
                className="delete-btn"
                onClick={() => handleDelete(item.id)}
                aria-label={`Delete ${item.name}`}
              >
                Delete
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default App
