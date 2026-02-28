import React from 'react';
import { motion } from 'framer-motion';

export default function MotionBackground() {
    return (
        <div className="motion-bg">
            {/* Deep blue/black base gradient */}
            <div className="bg-base" />

            {/* Animated glowing orbs representing disaster 'hotspots' or 'weather fronts' */}

            {/* Red/Orange glow (Heat/Wildfire/Crisis) */}
            <motion.div
                className="orb orb-red"
                animate={{
                    x: [0, 100, -50, 0],
                    y: [0, -50, 100, 0],
                    scale: [1, 1.2, 0.8, 1],
                    opacity: [0.3, 0.5, 0.2, 0.3],
                }}
                transition={{ duration: 25, repeat: Infinity, ease: "easeInOut" }}
            />

            {/* Blue/Cyan glow (Floods/Weather systems) */}
            <motion.div
                className="orb orb-blue"
                animate={{
                    x: [0, -150, 100, 0],
                    y: [0, 100, -50, 0],
                    scale: [0.8, 1.3, 1, 0.8],
                    opacity: [0.2, 0.4, 0.1, 0.2],
                }}
                transition={{ duration: 35, repeat: Infinity, ease: "easeInOut" }}
            />

            {/* Amber glow (Alerts/Droughts) */}
            <motion.div
                className="orb orb-amber"
                animate={{
                    x: [0, 50, -100, 0],
                    y: [0, 150, 50, 0],
                    scale: [1, 0.9, 1.4, 1],
                    opacity: [0.1, 0.3, 0.15, 0.1],
                }}
                transition={{ duration: 30, repeat: Infinity, ease: "easeInOut" }}
            />

            {/* Grid overlay for a 'command center' tactical feel */}
            <div className="bg-grid" />
        </div>
    );
}
