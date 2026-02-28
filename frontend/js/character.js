/**
 * Three.js + VRM character controller with idle animations and lip sync.
 */

import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

let scene, camera, renderer, vrm, clock, controls;
let initialized = false;
let fallbackMode = false;

// Animation state
let currentAudioLevel = 0;
let targetAudioLevel = 0;
let currentExpression = 'neutral';
let aiSpeaking = false;

// P-VRM-001: Smooth expression transition state (lerp)
const EMOTION_PRESETS = ['happy', 'angry', 'sad', 'surprised', 'relaxed'];
let expressionTargets = {};  // target weights for emotion presets
let expressionCurrent = {};  // current interpolated weights

// Blink state
let blinkTimer = 0;
let blinkInterval = 3.0; // seconds between blinks
let isBlinking = false;
let blinkPhase = 0;

// Head idle state
let headIdleTime = 0;

// Gesture animation state
let activeGesture = null;
let gestureProgress = 0;
let gestureOriginalRotations = {}; // Store multiple bone rotations

// Emoji mappings for fallback
const EXPRESSION_EMOJI = {
    'neutral': '🤖', 'happy': '😊', 'thinking': '🤔',
    'encouraging': '😄', 'surprised': '😲',
};

async function initCharacter() {
    const canvas = document.getElementById('character-canvas');
    const container = document.getElementById('character-container');
    const fallback = document.getElementById('character-fallback');

    try {
        scene = new THREE.Scene();
        scene.background = new THREE.Color(0xf5f7fa);

        camera = new THREE.PerspectiveCamera(
            25,
            container.clientWidth / container.clientHeight,
            0.1,
            20
        );
        camera.position.set(0, 1.25, 1.5);
        camera.lookAt(0, 1.25, 0);

        renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
        renderer.setSize(container.clientWidth, container.clientHeight);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.outputColorSpace = THREE.SRGBColorSpace;

        // OrbitControls - allow user to rotate and zoom camera
        controls = new OrbitControls(camera, canvas);
        controls.target.set(0, 1.25, 0); // Head height
        controls.minDistance = 1.0;
        controls.maxDistance = 4.0;
        controls.minPolarAngle = 0.5; // Prevent looking from below
        controls.maxPolarAngle = 1.5;
        controls.enableDamping = true;
        controls.dampingFactor = 0.05;
        controls.update();

        // Lighting - brighter for light theme
        const ambientLight = new THREE.AmbientLight(0xffffff, 1.0);
        scene.add(ambientLight);

        const mainLight = new THREE.DirectionalLight(0xffffff, 0.8);
        mainLight.position.set(1, 2, 2);
        scene.add(mainLight);

        const fillLight = new THREE.DirectionalLight(0xdde4ff, 0.4);
        fillLight.position.set(-1, 1, 0);
        scene.add(fillLight);

        clock = new THREE.Clock();

        await loadVRM();

        if (vrm) {
            canvas.style.display = 'block';
            fallback.style.display = 'none';
            initialized = true;

            // P-VRM-001: Initialize expression lerp state after VRM load
            EMOTION_PRESETS.forEach(preset => {
                expressionTargets[preset] = 0;
                expressionCurrent[preset] = 0;
            });

            // Log available expressions for debugging
            if (vrm.expressionManager) {
                const names = vrm.expressionManager.expressions
                    ? vrm.expressionManager.expressions.map(e => e.expressionName)
                    : [];
                console.log('VRM expressions available:', names);
            }

            animate();
        } else {
            throw new Error('No VRM model loaded');
        }
    } catch (e) {
        console.log('Using fallback avatar mode:', e.message);
        fallbackMode = true;
        if (canvas) canvas.style.display = 'none';
        if (fallback) fallback.style.display = 'flex';
    }

    window.addEventListener('resize', () => {
        if (initialized && renderer) {
            const w = container.clientWidth;
            const h = container.clientHeight;
            camera.aspect = w / h;
            camera.updateProjectionMatrix();
            renderer.setSize(w, h);
        }
    });
}

async function loadVRM() {
    const loader = new GLTFLoader();
    const { VRMLoaderPlugin } = await import('@pixiv/three-vrm');
    loader.register((parser) => new VRMLoaderPlugin(parser));

    return new Promise((resolve) => {
        loader.load(
            '/models/avatar.vrm',
            (gltf) => {
                vrm = gltf.userData.vrm;
                if (vrm) {
                    scene.add(vrm.scene);
                    vrm.scene.rotation.y = Math.PI;
                    disableExpressionOverrides();
                    console.log('VRM model loaded successfully');
                    logDiagnostics();
                }
                resolve(vrm);
            },
            (progress) => {
                if (progress.total > 0) {
                    const pct = Math.round((progress.loaded / progress.total) * 100);
                    console.log(`VRM loading: ${pct}%`);
                }
            },
            (error) => {
                console.log('VRM model not found:', error);
                resolve(null);
            }
        );
    });
}

function disableExpressionOverrides() {
    if (!vrm || !vrm.expressionManager) return;
    const expressions = vrm.expressionManager.expressions || [];
    expressions.forEach(expr => {
        if (expr.overrideMouth !== undefined) {
            expr.overrideMouth = 'none';
        }
        if (expr.overrideBlink !== undefined) {
            expr.overrideBlink = 'none';
        }
    });
    console.log('Expression overrides disabled for lip sync compatibility');
}

function logDiagnostics() {
    if (!vrm) return;

    console.log('=== VRM Model Diagnostics ===');

    // Bone availability
    if (vrm.humanoid) {
        const boneNames = ['head', 'rightUpperArm', 'rightLowerArm',
                           'leftUpperArm', 'leftLowerArm', 'spine'];
        console.log('Bones:');
        boneNames.forEach(name => {
            const bone = vrm.humanoid.getNormalizedBoneNode(name);
            console.log(`  ${name}:`, bone ? '✓ found' : '✗ MISSING');
        });
    }

    // Expression availability
    if (vrm.expressionManager) {
        const expressions = vrm.expressionManager.expressions || [];
        console.log('Expressions:');
        expressions.forEach(expr => {
            console.log(`  ${expr.expressionName}:`, {
                overrideMouth: expr.overrideMouth,
                overrideBlink: expr.overrideBlink,
            });
        });
    }

    console.log('=========================');
}

async function loadModel(source) {
    // source: '/models/avatar.vrm' or blob URL
    const wasAnimating = initialized;
    initialized = false; // Pause animation loop

    // Unload current
    if (vrm) {
        activeGesture = null;
        gestureProgress = 0;
        gestureOriginalRotations = {};
        currentAudioLevel = 0;
        targetAudioLevel = 0;

        scene.remove(vrm.scene);
        vrm.scene.traverse((obj) => {
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) {
                const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
                mats.forEach(mat => {
                    if (mat.map) mat.map.dispose();
                    mat.dispose();
                });
            }
        });
        vrm = null;
    }

    // Load new
    const loader = new GLTFLoader();
    const { VRMLoaderPlugin } = await import('@pixiv/three-vrm');
    loader.register((parser) => new VRMLoaderPlugin(parser));

    return new Promise((resolve, reject) => {
        loader.load(source,
            (gltf) => {
                vrm = gltf.userData.vrm;
                if (vrm) {
                    scene.add(vrm.scene);
                    vrm.scene.rotation.y = Math.PI;
                    disableExpressionOverrides(); // Phase 1 の修正を新モデルにも適用
                    // P-VRM-001: Reset expression lerp state for new model
                    EMOTION_PRESETS.forEach(preset => {
                        expressionTargets[preset] = 0;
                        expressionCurrent[preset] = 0;
                    });
                    initialized = true;
                    if (!wasAnimating) animate(); // 初回のみ animate 開始
                    console.log('VRM model switched successfully');
                    logDiagnostics();
                    resolve(vrm);
                } else {
                    reject(new Error('VRM data not found in file'));
                }
            },
            null,
            (error) => reject(error)
        );
    });
}

function animate() {
    if (!initialized) return;
    requestAnimationFrame(animate);

    const delta = clock.getDelta();
    const time = clock.getElapsedTime();

    if (vrm) {
        // --- Idle Breathing ---
        if (vrm.scene) {
            vrm.scene.position.y = Math.sin(time * 1.2) * 0.003;
        }

        // --- Blinking ---
        updateBlink(delta);

        // --- Head idle sway ---
        updateHeadIdle(time);

        // --- Lip sync ---
        updateLipSync(delta);

        // --- Gesture animation ---
        updateGesture(delta);

        // P-VRM-001: Smooth expression transitions via lerp
        // delta * 8 ≈ 0.125s to converge; Math.min(..., 1) prevents overshoot
        if (vrm.expressionManager) {
            EMOTION_PRESETS.forEach(preset => {
                const target = expressionTargets[preset] ?? 0;
                const current = expressionCurrent[preset] ?? 0;
                const next = current + (target - current) * Math.min(delta * 8, 1);
                expressionCurrent[preset] = next;
                vrm.expressionManager.setValue(preset, next);
            });
        }

        // --- Update VRM ---
        vrm.update(delta);
    }

    // --- Update OrbitControls ---
    if (controls) {
        controls.update();
    }

    renderer.render(scene, camera);
}

// ========== BLINK ==========

function updateBlink(delta) {
    if (!vrm || !vrm.expressionManager) return;

    blinkTimer += delta;

    if (!isBlinking && blinkTimer >= blinkInterval) {
        isBlinking = true;
        blinkPhase = 0;
        blinkTimer = 0;
        // Randomize next blink interval (2-5s)
        blinkInterval = 2.0 + Math.random() * 3.0;
        // Occasionally double-blink
        if (Math.random() < 0.2) {
            blinkInterval = 0.3;
        }
    }

    if (isBlinking) {
        blinkPhase += delta * 8.0; // ~0.25s for full blink
        let blinkValue;
        if (blinkPhase < 1.0) {
            blinkValue = blinkPhase; // closing
        } else if (blinkPhase < 2.0) {
            blinkValue = 2.0 - blinkPhase; // opening
        } else {
            blinkValue = 0;
            isBlinking = false;
        }
        vrm.expressionManager.setValue('blink', Math.max(0, Math.min(1, blinkValue)));
    }
}

// ========== HEAD IDLE ==========

function updateHeadIdle(time) {
    if (!vrm || !vrm.humanoid) return;

    const head = vrm.humanoid.getNormalizedBoneNode('head');
    if (!head) return;

    // Only apply idle when no gesture is active
    if (activeGesture) return;

    // Gentle swaying using multiple sine waves
    const baseX = Math.sin(time * 0.3) * 0.02 + Math.sin(time * 0.7) * 0.01;
    const baseY = Math.sin(time * 0.2) * 0.03 + Math.cos(time * 0.5) * 0.01;
    const baseZ = Math.sin(time * 0.4) * 0.01;

    head.rotation.x = baseX;
    head.rotation.y = baseY;
    head.rotation.z = baseZ;
}

// ========== LIP SYNC ==========

function updateLipSync(delta) {
    if (!vrm || !vrm.expressionManager) return;

    // Smoothly interpolate audio level
    currentAudioLevel += (targetAudioLevel - currentAudioLevel) * Math.min(1, delta * 15);

    if (aiSpeaking && currentAudioLevel > 0.01) {
        // Map audio level to mouth shapes
        const mouthOpen = Math.min(1.0, currentAudioLevel * 1.5);

        // Cycle through vowel shapes for natural look
        const time = clock.getElapsedTime();
        const vowelCycle = Math.sin(time * 12) * 0.5 + 0.5;

        // Use 'aa' (mouth open) as primary, blend with others
        vrm.expressionManager.setValue('aa', mouthOpen * 0.8);
        vrm.expressionManager.setValue('oh', mouthOpen * vowelCycle * 0.3);
        vrm.expressionManager.setValue('ee', mouthOpen * (1 - vowelCycle) * 0.2);
    } else {
        // Close mouth when not speaking
        vrm.expressionManager.setValue('aa', Math.max(0, currentAudioLevel * 0.5));
        vrm.expressionManager.setValue('oh', 0);
        vrm.expressionManager.setValue('ee', 0);
    }
}

// ========== GESTURE ==========

// Easing function (ease-in-out cubic)
function easeInOutCubic(t) {
    return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

// Store original bone rotations before gesture starts
function saveOriginalRotations() {
    if (!vrm || !vrm.humanoid) return;

    const bones = [
        'head', 'rightUpperArm', 'rightLowerArm',
        'leftUpperArm', 'leftLowerArm', 'spine'
    ];

    gestureOriginalRotations = {};
    bones.forEach(boneName => {
        const bone = vrm.humanoid.getNormalizedBoneNode(boneName);
        if (bone) {
            gestureOriginalRotations[boneName] = {
                x: bone.rotation.x,
                y: bone.rotation.y,
                z: bone.rotation.z
            };
        }
    });
}

// Restore bones to original rotations
function restoreBoneRotations() {
    if (!vrm || !vrm.humanoid) return;

    Object.keys(gestureOriginalRotations).forEach(boneName => {
        const bone = vrm.humanoid.getNormalizedBoneNode(boneName);
        if (bone && gestureOriginalRotations[boneName]) {
            bone.rotation.x = gestureOriginalRotations[boneName].x;
            bone.rotation.y = gestureOriginalRotations[boneName].y;
            bone.rotation.z = gestureOriginalRotations[boneName].z;
        }
    });
}

// Set idle pose (reset all gesture bones to rest position)
function setIdlePose() {
    if (!vrm || !vrm.humanoid) return;
    // Reset all gesture bones to rest position
    const bones = ['rightUpperArm', 'rightLowerArm', 'leftUpperArm', 'leftLowerArm', 'spine'];
    bones.forEach(name => {
        const bone = vrm.humanoid.getNormalizedBoneNode(name);
        if (bone) {
            bone.rotation.set(0, 0, 0);
        }
    });
}

function updateGesture(delta) {
    if (!activeGesture || !vrm || !vrm.humanoid) return;

    gestureProgress += delta;

    // Get bones with null checks
    const head = vrm.humanoid.getNormalizedBoneNode('head');
    const rightUpperArm = vrm.humanoid.getNormalizedBoneNode('rightUpperArm');
    const rightLowerArm = vrm.humanoid.getNormalizedBoneNode('rightLowerArm');
    const leftUpperArm = vrm.humanoid.getNormalizedBoneNode('leftUpperArm');
    const leftLowerArm = vrm.humanoid.getNormalizedBoneNode('leftLowerArm');
    const spine = vrm.humanoid.getNormalizedBoneNode('spine');

    if (activeGesture === 'nod') {
        // Keep as head-only (natural)
        if (!head) {
            activeGesture = null;
            return;
        }
        const duration = 0.8;
        if (gestureProgress < duration) {
            const t = gestureProgress / duration;
            const nodAngle = Math.sin(t * Math.PI * 3) * 0.2;
            head.rotation.x = nodAngle;
        } else {
            setIdlePose();
            activeGesture = null;
        }

    } else if (activeGesture === 'wave') {
        // Right arm oscillation
        if (!rightUpperArm) {
            activeGesture = null;
            return;
        }
        const duration = 1.5;
        if (gestureProgress < duration) {
            const t = gestureProgress / duration;
            const oscillation = Math.sin(t * Math.PI * 4); // 4 waves
            const zRotation = -Math.PI / 3 + (oscillation * Math.PI / 12); // -60° ± 15°
            rightUpperArm.rotation.z = gestureOriginalRotations.rightUpperArm.z + zRotation;
            if (rightLowerArm) {
                rightLowerArm.rotation.z = gestureOriginalRotations.rightLowerArm.z + (oscillation * 0.1);
            }
        } else {
            setIdlePose();
            activeGesture = null;
        }

    } else if (activeGesture === 'thumbs_up') {
        // Right arm raised with thumb up pose
        if (!rightUpperArm || !rightLowerArm) {
            activeGesture = null;
            return;
        }
        const duration = 1.0;
        if (gestureProgress < duration) {
            const t = easeInOutCubic(Math.min(1, gestureProgress / (duration * 0.3))); // ease in
            const easeOut = easeInOutCubic(Math.max(0, (gestureProgress - duration * 0.7) / (duration * 0.3))); // ease out
            const blend = t * (1 - easeOut);

            rightUpperArm.rotation.z = gestureOriginalRotations.rightUpperArm.z + (-Math.PI / 4 * blend); // -45°
            rightLowerArm.rotation.x = gestureOriginalRotations.rightLowerArm.x + (Math.PI / 2 * blend); // 90°
            if (head) {
                head.rotation.x = -0.1 * blend; // slight look up
            }
        } else {
            setIdlePose();
            activeGesture = null;
        }

    } else if (activeGesture === 'explain') {
        // Both arms outward with subtle oscillation
        if (!rightUpperArm && !leftUpperArm) {
            activeGesture = null;
            return;
        }
        const duration = 1.2;
        if (gestureProgress < duration) {
            const t = gestureProgress / duration;
            const vibration = Math.sin(t * Math.PI * 8) * 0.05; // subtle oscillation

            if (rightUpperArm) {
                rightUpperArm.rotation.z = gestureOriginalRotations.rightUpperArm.z + (-Math.PI / 6 + vibration); // -30° + vibration
            }
            if (leftUpperArm) {
                leftUpperArm.rotation.z = gestureOriginalRotations.leftUpperArm.z + (Math.PI / 6 - vibration); // +30° - vibration
            }
        } else {
            setIdlePose();
            activeGesture = null;
        }

    } else if (activeGesture === 'listen') {
        // Head tilt + body lean
        if (!head) {
            activeGesture = null;
            return;
        }
        const duration = 0.8;
        if (gestureProgress < duration) {
            const t = easeInOutCubic(gestureProgress / duration);
            head.rotation.z = t * 0.15; // tilt head
            if (spine) {
                spine.rotation.z = gestureOriginalRotations.spine.z + (t * 0.08); // slight body lean
            }
        } else {
            setIdlePose();
            activeGesture = null;
        }

    } else if (activeGesture === 'shrug') {
        // Shrug shoulders - both shoulders up
        if (!rightUpperArm && !leftUpperArm) {
            activeGesture = null;
            return;
        }
        const duration = 1.0;
        if (gestureProgress < duration) {
            const t = easeInOutCubic(Math.min(1, gestureProgress / (duration * 0.4))); // ease in
            const easeOut = easeInOutCubic(Math.max(0, (gestureProgress - duration * 0.6) / (duration * 0.4))); // ease out
            const blend = t * (1 - easeOut);

            if (rightUpperArm) {
                rightUpperArm.rotation.z = gestureOriginalRotations.rightUpperArm.z + (Math.PI / 8 * blend); // +22.5°
            }
            if (leftUpperArm) {
                leftUpperArm.rotation.z = gestureOriginalRotations.leftUpperArm.z + (-Math.PI / 8 * blend); // -22.5°
            }
        } else {
            setIdlePose();
            activeGesture = null;
        }

    } else if (activeGesture === 'thinking_pose') {
        // Right hand to chin
        if (!rightUpperArm || !rightLowerArm) {
            activeGesture = null;
            return;
        }
        const duration = 1.2;
        if (gestureProgress < duration) {
            const t = easeInOutCubic(Math.min(1, gestureProgress / (duration * 0.3))); // ease in
            rightUpperArm.rotation.x = gestureOriginalRotations.rightUpperArm.x + (Math.PI / 6 * t); // +30° (forward)
            rightUpperArm.rotation.z = gestureOriginalRotations.rightUpperArm.z + (-Math.PI / 6 * t); // -30° (toward body)
            rightLowerArm.rotation.x = gestureOriginalRotations.rightLowerArm.x + (Math.PI / 2 * t); // +90° (bend elbow)
        } else {
            setIdlePose();
            activeGesture = null;
        }

    } else if (activeGesture === 'open_palms') {
        // Both arms forward with palms up
        if (!rightUpperArm && !leftUpperArm) {
            activeGesture = null;
            return;
        }
        const duration = 1.0;
        if (gestureProgress < duration) {
            const t = easeInOutCubic(Math.min(1, gestureProgress / (duration * 0.3))); // ease in
            const easeOut = easeInOutCubic(Math.max(0, (gestureProgress - duration * 0.7) / (duration * 0.3))); // ease out
            const blend = t * (1 - easeOut);

            if (rightUpperArm) {
                rightUpperArm.rotation.x = gestureOriginalRotations.rightUpperArm.x + (Math.PI / 4 * blend); // +45° (forward)
                rightUpperArm.rotation.z = gestureOriginalRotations.rightUpperArm.z + (-Math.PI / 12 * blend); // -15° (slightly outward)
            }
            if (leftUpperArm) {
                leftUpperArm.rotation.x = gestureOriginalRotations.leftUpperArm.x + (Math.PI / 4 * blend); // +45° (forward)
                leftUpperArm.rotation.z = gestureOriginalRotations.leftUpperArm.z + (Math.PI / 12 * blend); // +15° (slightly outward)
            }
            if (rightLowerArm) {
                rightLowerArm.rotation.y = gestureOriginalRotations.rightLowerArm.y + (Math.PI / 6 * blend); // palm up rotation
            }
            if (leftLowerArm) {
                leftLowerArm.rotation.y = gestureOriginalRotations.leftLowerArm.y + (-Math.PI / 6 * blend); // palm up rotation
            }
        } else {
            setIdlePose();
            activeGesture = null;
        }

    } else if (activeGesture === 'head_shake') {
        // Head shake - left/right oscillation
        if (!head) {
            activeGesture = null;
            return;
        }
        const duration = 1.0;
        if (gestureProgress < duration) {
            const t = gestureProgress / duration;
            const shakeAngle = Math.sin(t * Math.PI * 4) * 0.2; // 4 shakes
            head.rotation.y = shakeAngle;
        } else {
            setIdlePose();
            activeGesture = null;
        }

    } else if (activeGesture === 'lean_forward') {
        // Lean forward - spine forward tilt
        if (!spine) {
            activeGesture = null;
            return;
        }
        const duration = 0.8;
        if (gestureProgress < duration) {
            const t = easeInOutCubic(gestureProgress / duration);
            spine.rotation.x = gestureOriginalRotations.spine.x + (t * 0.15); // +~8.6° forward
        } else {
            setIdlePose();
            activeGesture = null;
        }

    } else if (activeGesture === 'celebration') {
        // Both arms raised with small vibration
        if (!rightUpperArm && !leftUpperArm) {
            activeGesture = null;
            return;
        }
        const duration = 1.5;
        if (gestureProgress < duration) {
            const t = gestureProgress / duration;
            const vibration = Math.sin(t * Math.PI * 12) * 0.05; // small vibration

            if (rightUpperArm) {
                rightUpperArm.rotation.z = gestureOriginalRotations.rightUpperArm.z + (-Math.PI / 2 + vibration); // -90° + vibration
            }
            if (leftUpperArm) {
                leftUpperArm.rotation.z = gestureOriginalRotations.leftUpperArm.z + (Math.PI / 2 - vibration); // +90° - vibration
            }
        } else {
            setIdlePose();
            activeGesture = null;
        }

    } else if (activeGesture === 'point') {
        // Point forward - right arm extended
        if (!rightUpperArm || !rightLowerArm) {
            activeGesture = null;
            return;
        }
        const duration = 1.0;
        if (gestureProgress < duration) {
            const t = easeInOutCubic(Math.min(1, gestureProgress / (duration * 0.3))); // ease in
            const easeOut = easeInOutCubic(Math.max(0, (gestureProgress - duration * 0.7) / (duration * 0.3))); // ease out
            const blend = t * (1 - easeOut);

            rightUpperArm.rotation.x = gestureOriginalRotations.rightUpperArm.x + (Math.PI / 4 * blend); // +45° (forward)
            rightUpperArm.rotation.z = gestureOriginalRotations.rightUpperArm.z + (-Math.PI / 6 * blend); // -30° (toward front)
            rightLowerArm.rotation.x = gestureOriginalRotations.rightLowerArm.x + (-Math.PI / 12 * blend); // -15° (straighten arm)
        } else {
            setIdlePose();
            activeGesture = null;
        }

    } else if (activeGesture === 'idle_rest') {
        // Immediate transition to idle pose
        setIdlePose();
        activeGesture = null;

    } else {
        setIdlePose();
        activeGesture = null;
    }
}

// ========== PUBLIC API ==========

function setExpression(expression) {
    if (fallbackMode) {
        const emoji = EXPRESSION_EMOJI[expression] || EXPRESSION_EMOJI['neutral'];
        const avatarEl = document.getElementById('avatar-face');
        const labelEl = document.getElementById('expression-label');
        if (avatarEl) avatarEl.textContent = emoji;
        if (labelEl) labelEl.textContent = expression;
        return;
    }

    if (!vrm || !vrm.expressionManager) return;

    currentExpression = expression;

    // P-VRM-001: Update emotion targets only — animate() handles lerp transitions
    // Reset all emotion targets (don't touch blink or mouth shapes)
    EMOTION_PRESETS.forEach(e => { expressionTargets[e] = 0; });

    const presetMap = {
        'happy': 'happy',
        'encouraging': 'happy',
        'surprised': 'surprised',
        'thinking': 'relaxed',
        'neutral': null, // no preset needed
    };

    const preset = presetMap[expression];
    if (preset) {
        // Reduce weight during speech to prevent mouth override
        const weight = aiSpeaking ? 0.35 : 0.7;
        expressionTargets[preset] = weight;
        // DO NOT call setValue directly here — animate() handles the lerp
    }

    console.log('Expression set:', expression);
}

function playGesture(gesture) {
    if (fallbackMode) {
        const avatarEl = document.getElementById('avatar-face');
        if (!avatarEl) return;
        avatarEl.classList.remove('gesture-nod', 'gesture-wave');
        void avatarEl.offsetWidth;
        avatarEl.classList.add(`gesture-${gesture}`);
        setTimeout(() => avatarEl.classList.remove(`gesture-${gesture}`), 1000);
        return;
    }

    if (!vrm) return;

    // Save current bone rotations before starting gesture
    saveOriginalRotations();

    activeGesture = gesture;
    gestureProgress = 0;
    console.log('Gesture played:', gesture);
}

function setAudioLevel(level) {
    targetAudioLevel = level;
}

function setAiSpeaking(speaking) {
    aiSpeaking = speaking;
    if (!speaking) {
        targetAudioLevel = 0;
    }
}

// Expose to global scope
window.CharacterController = {
    init: initCharacter,
    setExpression,
    playGesture,
    setAudioLevel,
    setAiSpeaking,
    loadModel,
};
