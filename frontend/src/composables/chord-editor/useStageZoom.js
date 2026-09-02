import { ref, computed, onMounted, onUnmounted } from 'vue'

export function useStageZoom(stageFrameRef, drag) {
  const zoom = ref(1)
  const ZOOM_MIN = 1
  const ZOOM_MAX = 2.5
  const ZOOM_STEP = 0.25
  const PAN_STEP = 90

  const stageStyle = computed(() =>
    zoom.value <= 1? {} : { width: `${zoom.value * 100}%`, maxWidth: 'none' }
  )

  function zoomIn() { zoom.value = Math.min(ZOOM_MAX, +(zoom.value + ZOOM_STEP).toFixed(2)) }
  function zoomOut() { zoom.value = Math.max(ZOOM_MIN, +(zoom.value - ZOOM_STEP).toFixed(2)) }
  function panBy(dx, dy) { stageFrameRef.value?.scrollBy({ left: dx, top: dy, behavior: 'smooth' }) }

  // 핀치 줌
  const activePointers = new Map()
  let pinchStartDist = 0, pinchStartZoom = 1
  const dist = pts => Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y)

  function onStagePointerDownCapture(e) {
    activePointers.set(e.pointerId, { x: e.clientX, y: e.clientY })
    if (activePointers.size === 2) {
      drag.value = null
      pinchStartDist = dist([...activePointers.values()])
      pinchStartZoom = zoom.value
    }
  }
  function onGlobalPointerMove(e) {
    if (!activePointers.has(e.pointerId)) return
    activePointers.set(e.pointerId, { x: e.clientX, y: e.clientY })
    if (activePointers.size < 2 || pinchStartDist <= 0) return
    const d = dist([...activePointers.values()])
    zoom.value = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, +(pinchStartZoom * (d / pinchStartDist)).toFixed(2)))
  }
  function onGlobalPointerUp(e) {
    activePointers.delete(e.pointerId)
    if (activePointers.size < 2) pinchStartDist = 0
  }

  onMounted(() => {
    window.addEventListener('pointermove', onGlobalPointerMove)
    window.addEventListener('pointerup', onGlobalPointerUp)
    window.addEventListener('pointercancel', onGlobalPointerUp)
  })
  onUnmounted(() => {
    window.removeEventListener('pointermove', onGlobalPointerMove)
    window.removeEventListener('pointerup', onGlobalPointerUp)
    window.removeEventListener('pointercancel', onGlobalPointerUp)
  })

  return { zoom, ZOOM_MIN, ZOOM_MAX, PAN_STEP, zoomIn, zoomOut, panBy, stageStyle, onStagePointerDownCapture }
}