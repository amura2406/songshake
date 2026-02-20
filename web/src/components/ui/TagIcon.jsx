import React from 'react';
import { getTagIcon } from '../../utils/tagIcons';

/**
 * Renders an icon for a tag based on its type and value.
 * Handles both Lucide React components and Material Icon ligatures.
 *
 * @param {{ type: 'genre'|'mood'|'instrument', value: string, size?: number, className?: string }} props
 */
const TagIcon = ({ type, value, size = 12, className = '' }) => {
    const result = getTagIcon(type, value);
    if (!result) return null;

    if (result.icon) {
        const Icon = result.icon;
        return <Icon size={size} className={`inline-block shrink-0 ${className}`} />;
    }

    if (result.materialIcon) {
        return (
            <span
                className={`material-icons inline-block shrink-0 leading-none ${className}`}
                style={{ fontSize: `${size}px` }}
            >
                {result.materialIcon}
            </span>
        );
    }

    return null;
};

export default TagIcon;
