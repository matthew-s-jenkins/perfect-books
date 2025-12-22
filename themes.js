/**
 * PERFECT BOOKS - THEME CONFIGURATION
 *
 * This file contains all theme color definitions.
 * Non-technical users can easily tweak colors here without touching the main code.
 *
 * HOW TO ADD A NEW THEME:
 * 1. Copy an existing theme object
 * 2. Change the name and colors
 * 3. Add it to the THEMES object at the bottom
 *
 * COLOR GUIDE:
 * - bg: Main background
 * - bgSecondary: Cards, panels
 * - bgTertiary: Inputs, dropdowns
 * - text: Primary text color
 * - textSecondary: Muted text
 * - border: Border colors
 * - primary: Main accent color (buttons, links)
 * - primaryHover: Hover state for primary
 * - success: Positive numbers, income
 * - danger: Negative numbers, expenses
 * - warning: Alerts, warnings
 */

const THEMES = {
    classic: {
        name: 'Classic',
        colors: {
            // Backgrounds
            bg: '#111827',           // gray-900
            bgSecondary: '#1f2937',  // gray-800
            bgTertiary: '#374151',   // gray-700
            bgHover: '#4b5563',      // gray-600

            // Text
            text: '#f9fafb',         // gray-50
            textSecondary: '#d1d5db', // gray-300
            textMuted: '#9ca3af',    // gray-400

            // Borders
            border: '#4b5563',       // gray-600
            borderLight: '#374151',  // gray-700

            // Primary accent (cyan)
            primary: '#06b6d4',      // cyan-500
            primaryHover: '#0891b2', // cyan-600
            primaryLight: '#22d3ee', // cyan-400

            // Status colors
            success: '#10b981',      // green-500
            successLight: '#34d399', // green-400
            danger: '#ef4444',       // red-500
            dangerLight: '#f87171',  // red-400
            warning: '#f59e0b',      // amber-500
            warningLight: '#fbbf24', // amber-400
        }
    },

    midnight: {
        name: 'Midnight',
        colors: {
            // Backgrounds (deep purple/indigo)
            bg: '#0f0820',           // Very dark purple
            bgSecondary: '#1a1033',  // Dark purple
            bgTertiary: '#2d1b4e',   // Medium dark purple
            bgHover: '#3d2563',      // Lighter purple

            // Text
            text: '#f0e6ff',         // Light purple tint
            textSecondary: '#c7b8ea', // Muted purple
            textMuted: '#9d8ec4',    // Muted purple

            // Borders
            border: '#4c3575',       // Purple border
            borderLight: '#3d2563',  // Lighter purple border

            // Primary accent (bright purple/magenta)
            primary: '#a855f7',      // purple-500
            primaryHover: '#9333ea', // purple-600
            primaryLight: '#c084fc', // purple-400

            // Status colors
            success: '#10b981',      // green-500
            successLight: '#34d399', // green-400
            danger: '#f43f5e',       // rose-500
            dangerLight: '#fb7185',  // rose-400
            warning: '#f59e0b',      // amber-500
            warningLight: '#fbbf24', // amber-400
        }
    },

    emerald: {
        name: 'Emerald',
        colors: {
            // Backgrounds (dark with green tint)
            bg: '#0a1410',           // Very dark green-black
            bgSecondary: '#0f2419',  // Dark green
            bgTertiary: '#1a3d2e',   // Medium dark green
            bgHover: '#27543f',      // Lighter green

            // Text
            text: '#f0fdf4',         // Light green tint
            textSecondary: '#d1fae5', // Muted green
            textMuted: '#a7f3d0',    // Muted green

            // Borders
            border: '#34704f',       // Green border
            borderLight: '#27543f',  // Lighter green border

            // Primary accent (emerald)
            primary: '#10b981',      // emerald-500
            primaryHover: '#059669', // emerald-600
            primaryLight: '#34d399', // emerald-400

            // Status colors
            success: '#22c55e',      // green-500
            successLight: '#4ade80', // green-400
            danger: '#ef4444',       // red-500
            dangerLight: '#f87171',  // red-400
            warning: '#f59e0b',      // amber-500
            warningLight: '#fbbf24', // amber-400
        }
    },

    amber: {
        name: 'Amber',
        colors: {
            // Backgrounds (warm brown/tan)
            bg: '#1c1410',           // Very dark brown
            bgSecondary: '#2d2318',  // Dark warm brown
            bgTertiary: '#44362a',   // Medium brown
            bgHover: '#5c4939',      // Lighter brown

            // Text
            text: '#fef3c7',         // Warm cream
            textSecondary: '#fde68a', // Light amber
            textMuted: '#fcd34d',    // Muted amber

            // Borders
            border: '#78644e',       // Tan border
            borderLight: '#5c4939',  // Lighter brown border

            // Primary accent (amber/orange)
            primary: '#f59e0b',      // amber-500
            primaryHover: '#d97706', // amber-600
            primaryLight: '#fbbf24', // amber-400

            // Status colors
            success: '#10b981',      // green-500
            successLight: '#34d399', // green-400
            danger: '#dc2626',       // red-600
            dangerLight: '#ef4444',  // red-500
            warning: '#ea580c',      // orange-600
            warningLight: '#f97316', // orange-500
        }
    },

    rose: {
        name: 'Rose',
        colors: {
            // Backgrounds (dark with pink tint)
            bg: '#1a0d14',           // Very dark rose
            bgSecondary: '#2d1823',  // Dark rose
            bgTertiary: '#4a2d3d',   // Medium dark rose
            bgHover: '#5e3a51',      // Lighter rose

            // Text
            text: '#fef2f2',         // Light rose tint
            textSecondary: '#fecdd3', // Muted pink
            textMuted: '#fda4af',    // Muted rose

            // Borders
            border: '#9f4d70',       // Rose border
            borderLight: '#7c3a5a',  // Lighter rose border

            // Primary accent (rose/pink)
            primary: '#f43f5e',      // rose-500
            primaryHover: '#e11d48', // rose-600
            primaryLight: '#fb7185', // rose-400

            // Status colors
            success: '#10b981',      // green-500
            successLight: '#34d399', // green-400
            danger: '#dc2626',       // red-600
            dangerLight: '#ef4444',  // red-500
            warning: '#f59e0b',      // amber-500
            warningLight: '#fbbf24', // amber-400
        }
    },

    slate: {
        name: 'Slate',
        colors: {
            // Backgrounds (true dark - very dark grays)
            bg: '#0f0f0f',           // Almost black
            bgSecondary: '#1a1a1a',  // Very dark gray
            bgTertiary: '#262626',   // Dark gray
            bgHover: '#333333',      // Medium gray

            // Text
            text: '#fafafa',         // Off white
            textSecondary: '#d4d4d4', // Light gray
            textMuted: '#a3a3a3',    // Muted gray

            // Borders
            border: '#404040',       // Gray border
            borderLight: '#333333',  // Lighter gray border

            // Primary accent (slate blue)
            primary: '#64748b',      // slate-500
            primaryHover: '#475569', // slate-600
            primaryLight: '#94a3b8', // slate-400

            // Status colors
            success: '#10b981',      // green-500
            successLight: '#34d399', // green-400
            danger: '#ef4444',       // red-500
            dangerLight: '#f87171',  // red-400
            warning: '#f59e0b',      // amber-500
            warningLight: '#fbbf24', // amber-400
        }
    }
};

// Default theme
const DEFAULT_THEME = 'classic';

// Export for use in the app
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { THEMES, DEFAULT_THEME };
}
