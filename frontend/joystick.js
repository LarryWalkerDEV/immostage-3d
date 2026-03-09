/**
 * Virtual dual joystick for 3D navigation.
 * Only renders on touch devices.
 *
 * Usage:
 *   import { createJoystick } from './joystick.js'
 *   const left = createJoystick(document.body, 'left')
 *   const right = createJoystick(document.body, 'right')
 *   // In game loop:
 *   const dx = left.getX()  // -1 .. 1 (strafe)
 *   const dy = left.getY()  // -1 .. 1 (forward/back)
 */

const OUTER_SIZE = 80  // px
const KNOB_SIZE = 40   // px
const MAX_OFFSET = (OUTER_SIZE - KNOB_SIZE) / 2  // 20px

function isTouchDevice() {
  return 'ontouchstart' in window || navigator.maxTouchPoints > 0
}

function injectStyles() {
  if (document.getElementById('joystick-styles')) return

  const style = document.createElement('style')
  style.id = 'joystick-styles'
  style.textContent = `
    .joystick {
      position: fixed;
      bottom: 30px;
      width: ${OUTER_SIZE}px;
      height: ${OUTER_SIZE}px;
      border-radius: 50%;
      border: 2px solid rgba(255, 255, 255, 0.3);
      background: rgba(0, 0, 0, 0.2);
      z-index: 50;
      touch-action: none;
      user-select: none;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .joystick-left {
      left: 30px;
    }
    .joystick-right {
      right: 30px;
    }
    .joystick-knob {
      position: absolute;
      width: ${KNOB_SIZE}px;
      height: ${KNOB_SIZE}px;
      border-radius: 50%;
      background: rgba(255, 255, 255, 0.5);
      pointer-events: none;
      transition: transform 0.05s ease;
    }
  `
  document.head.appendChild(style)
}

/**
 * Creates a virtual joystick and appends it to the given container.
 *
 * @param {HTMLElement} container - DOM element to append the joystick to
 * @param {'left' | 'right'} side - Which side to place the joystick
 * @returns {{ getX: () => number, getY: () => number, destroy: () => void }}
 */
export function createJoystick(container, side = 'left') {
  // Only show on touch devices
  if (!isTouchDevice()) {
    return { getX: () => 0, getY: () => 0, destroy: () => {} }
  }

  injectStyles()

  const outer = document.createElement('div')
  outer.className = `joystick joystick-${side}`

  const knob = document.createElement('div')
  knob.className = 'joystick-knob'
  outer.appendChild(knob)

  container.appendChild(outer)

  let activeTouchId = null
  let originX = 0
  let originY = 0
  let currentX = 0
  let currentY = 0

  function getCenter() {
    const rect = outer.getBoundingClientRect()
    return {
      x: rect.left + rect.width / 2,
      y: rect.top + rect.height / 2,
    }
  }

  function updateKnob(dx, dy) {
    const dist = Math.sqrt(dx * dx + dy * dy)
    if (dist > MAX_OFFSET) {
      const scale = MAX_OFFSET / dist
      dx *= scale
      dy *= scale
    }
    currentX = dx / MAX_OFFSET
    currentY = dy / MAX_OFFSET
    knob.style.transform = `translate(${dx}px, ${dy}px)`
  }

  function resetKnob() {
    currentX = 0
    currentY = 0
    activeTouchId = null
    knob.style.transform = 'translate(0px, 0px)'
  }

  function onTouchStart(e) {
    if (activeTouchId !== null) return
    const touch = e.changedTouches[0]
    activeTouchId = touch.identifier
    const center = getCenter()
    originX = center.x
    originY = center.y
    updateKnob(touch.clientX - originX, touch.clientY - originY)
    e.preventDefault()
  }

  function onTouchMove(e) {
    for (const touch of e.changedTouches) {
      if (touch.identifier === activeTouchId) {
        updateKnob(touch.clientX - originX, touch.clientY - originY)
        break
      }
    }
    e.preventDefault()
  }

  function onTouchEnd(e) {
    for (const touch of e.changedTouches) {
      if (touch.identifier === activeTouchId) {
        resetKnob()
        break
      }
    }
    e.preventDefault()
  }

  outer.addEventListener('touchstart', onTouchStart, { passive: false })
  outer.addEventListener('touchmove', onTouchMove, { passive: false })
  outer.addEventListener('touchend', onTouchEnd, { passive: false })
  outer.addEventListener('touchcancel', onTouchEnd, { passive: false })

  function destroy() {
    outer.removeEventListener('touchstart', onTouchStart)
    outer.removeEventListener('touchmove', onTouchMove)
    outer.removeEventListener('touchend', onTouchEnd)
    outer.removeEventListener('touchcancel', onTouchEnd)
    outer.remove()
  }

  return {
    /** Normalized horizontal axis: -1 (left/strafe-left) .. 1 (right/strafe-right) */
    getX: () => currentX,
    /** Normalized vertical axis: -1 (up/forward) .. 1 (down/back) */
    getY: () => currentY,
    destroy,
  }
}
