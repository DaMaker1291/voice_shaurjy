"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

interface SceneData {
  origin?: string;
  destinations?: string[];
  flight_paths?: number[][];
}

export default function GlobeSimulation({ data, progress }: { data?: SceneData; progress?: number }) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const w = container.clientWidth || 400;
    const h = container.clientHeight || 400;
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, w / h, 0.1, 100);
    camera.position.set(0, 1, 6);

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setSize(w, h);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    // ── Globe ───────────────────────────────────────────────
    const globeGeo = new THREE.SphereGeometry(2, 48, 48);
    const globeMat = new THREE.MeshBasicMaterial({
      color: 0x4466aa,
      wireframe: true,
      transparent: true,
      opacity: 0.25,
    });
    const globe = new THREE.Mesh(globeGeo, globeMat);
    scene.add(globe);

    // Earth surface (subtle blue sphere)
    const surfaceMat = new THREE.MeshBasicMaterial({
      color: 0x224488,
      transparent: true,
      opacity: 0.12,
    });
    const surface = new THREE.Mesh(new THREE.SphereGeometry(1.98, 32, 32), surfaceMat);
    scene.add(surface);

    // Latitude/longitude grid
    const gridMat = new THREE.LineBasicMaterial({ color: 0x4466aa, transparent: true, opacity: 0.15 });
    for (let lat = -80; lat <= 80; lat += 20) {
      const phi = (90 - lat) * Math.PI / 180;
      const pts: THREE.Vector3[] = [];
      for (let lng = 0; lng <= 360; lng += 5) {
        const theta = lng * Math.PI / 180;
        pts.push(new THREE.Vector3(
          2 * Math.sin(phi) * Math.cos(theta),
          2 * Math.cos(phi),
          2 * Math.sin(phi) * Math.sin(theta)
        ));
      }
      scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), gridMat));
    }
    for (let lng = 0; lng < 360; lng += 30) {
      const theta = lng * Math.PI / 180;
      const pts: THREE.Vector3[] = [];
      for (let lat = -85; lat <= 85; lat += 3) {
        const phi = (90 - lat) * Math.PI / 180;
        pts.push(new THREE.Vector3(
          2 * Math.sin(phi) * Math.cos(theta),
          2 * Math.cos(phi),
          2 * Math.sin(phi) * Math.sin(theta)
        ));
      }
      scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), gridMat));
    }

    // ── Destination markers ─────────────────────────────────
    const markers: THREE.Mesh[] = [];
    const dests = data?.destinations || ["Paris", "Tokyo", "New York"];
    const positions = [
      new THREE.Vector3(0.8, 0.5, 1.6),   // ~Paris
      new THREE.Vector3(-1.2, -0.3, 1.4), // ~Tokyo
      new THREE.Vector3(-0.5, 1.0, -1.7), // ~NYC
      new THREE.Vector3(1.5, -0.8, -0.5), // ~Sydney
      new THREE.Vector3(0.3, -1.2, 1.3),  // ~Brazil
    ];

    dests.slice(0, 5).forEach((name, i) => {
      const pos = positions[i % positions.length].clone().normalize().multiplyScalar(2.05);
      const markerMat = new THREE.MeshBasicMaterial({ color: 0xff6644, transparent: true, opacity: 0.9 });
      const marker = new THREE.Mesh(new THREE.SphereGeometry(0.08, 8, 8), markerMat);
      marker.position.copy(pos);
      scene.add(marker);
      markers.push(marker);

      // Pulse ring
      const ringMat = new THREE.MeshBasicMaterial({
        color: 0xff6644, transparent: true, opacity: 0.2, side: THREE.DoubleSide,
      });
      const ring = new THREE.Mesh(new THREE.RingGeometry(0.12, 0.18, 16), ringMat);
      ring.position.copy(pos);
      scene.add(ring);
      markers.push(ring as any);
    });

    // ── Flight arcs ─────────────────────────────────────────
    const arcs: THREE.Line[] = [];
    for (let i = 0; i < Math.min(3, dests.length - 1); i++) {
      const from = positions[i % positions.length].normalize().multiplyScalar(2);
      const to = positions[(i + 1) % positions.length].normalize().multiplyScalar(2);
      const mid = from.clone().add(to).multiplyScalar(0.5).normalize().multiplyScalar(2.8);
      const curve = new THREE.QuadraticBezierCurve3(from, mid, to);
      const pts = curve.getPoints(24);
      const mat = new THREE.LineBasicMaterial({
        color: 0x44ddff,
        transparent: true,
        opacity: 0.3,
        linewidth: 1,
      });
      const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), mat);
      scene.add(line);
      arcs.push(line);
    }

    // ── Particles ───────────────────────────────────────────
    const particleCount = 200;
    const pGeo = new THREE.BufferGeometry();
    const pPos = new Float32Array(particleCount * 3);
    for (let i = 0; i < particleCount * 3; i++) pPos[i] = (Math.random() - 0.5) * 8;
    pGeo.setAttribute("position", new THREE.BufferAttribute(pPos, 3));
    const pMat = new THREE.PointsMaterial({
      color: 0x6688dd,
      size: 0.015,
      transparent: true,
      opacity: 0.2,
      blending: THREE.AdditiveBlending,
    });
    const particles = new THREE.Points(pGeo, pMat);
    scene.add(particles);

    // ── Animation ───────────────────────────────────────────
    let time = 0;
    const animate = () => {
      requestAnimationFrame(animate);
      time += 0.003;

      globe.rotation.y = time * 0.2;
      surface.rotation.y = time * 0.2;

      // Pulse markers
      markers.forEach((m, i) => {
        m.scale.setScalar(1 + Math.sin(time * 2 + i) * 0.2);
        if (i % 2 === 1) (m.material as THREE.MeshBasicMaterial).opacity = 0.1 + Math.sin(time * 2 + i) * 0.1;
      });

      // Animate arc opacity
      arcs.forEach((a, i) => {
        (a.material as THREE.LineBasicMaterial).opacity = 0.2 + Math.sin(time + i * 2) * 0.15;
      });

      particles.rotation.y = time * 0.05;

      renderer.render(scene, camera);
    };
    animate();

    const resize = () => {
      const w2 = container.clientWidth;
      const h2 = container.clientHeight;
      renderer.setSize(w2, h2);
      camera.aspect = w2 / h2;
      camera.updateProjectionMatrix();
    };
    window.addEventListener("resize", resize);

    return () => {
      window.removeEventListener("resize", resize);
      container.removeChild(renderer.domElement);
      renderer.dispose();
    };
  }, [data?.destinations?.join(",")]);

  return (
    <div ref={containerRef} className="w-full h-full min-h-[300px]" />
  );
}
